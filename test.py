import unittest
from mock import MagicMock
from typeform import *

OPTIONS = {
    # no-op logger during tests
    'logger': lambda *args: None
}

HEADERS = {'authorization': 'Bearer someToken'}


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = {}

    def __iter__(self):
        return iter(self.json_data)

    def json(self):
        return self.json_data

    def url(self):
        return ''

    def raise_for_status(self):
        if self.status_code > 400:
            raise requests.exceptions.RequestException


class TestMockResponse(unittest.TestCase):
    def test_iter(self):
        obj = {}
        mock = MockResponse(obj, 0)
        self.assertIsInstance(mock.__iter__(), type(obj.iterkeys()))

    def test_url(self):
        mock = MockResponse({}, 0)
        self.assertEqual(mock.url(), '')


class TestTypeform(unittest.TestCase):

    def test_destination(self):
        source = {'key': 'TypeformAPIKey'}
        Typeform(source, OPTIONS)
        dest = '{}_{}'.format(DESTINATION, DESTINATION_POSTFIX)
        self.assertEqual(source['destination'], dest)

    def test_results(self):
        form_name = 'Test Survey'
        source = {
            'access_token': 'TypefromToken',
            'forms': [{'value': 'abc', 'name': form_name}]
        }

        # mock the returned responses from the server
        res = generate_form_results(1)
        requests.get = MagicMock(return_value=MockResponse(res, 200))

        stream = Typeform(source, OPTIONS)

        results = stream.read()

        expected = [{
            '__completed': True,
            '__table': form_name,
            'answers': [
                {
                    'field_type': 'short_text',
                    'text': 'some_answer1',
                    'field_id': 'quetion1_id',
                    '__parent_id': 0,
                    'type': 'text',
                    'id': '0-quetion1_id'
                },
                {
                    'field_type': 'multiple_choice',
                    '__parent_id': 0,
                    'field_id': 'quetion2_id',
                    'choice_label': 'Agree',
                    'type': 'choice',
                    'id': '0-quetion2_id'
                }
            ],
            'token': 0,
            'id': 0,
            'metadata': {'someData': 'data'}
        }]

        self.assertEqual(results, expected)

    def test_results_not_completed(self):
        form_name = 'Test Survey'
        source = {
            'access_token': 'TypefromToken',
            'forms': [{'value': 'abc', 'name': form_name}]
        }

        # mock the returned responses from the server
        res = generate_form_results_not_completed(1)
        requests.get = MagicMock(return_value=MockResponse(res, 200))

        stream = Typeform(source, OPTIONS)

        results = stream.read()

        expected = [{
            '__completed': False,
            '__table': form_name,
            'answers': [],
            'token': 0,
            'id': 0,
            'metadata': {'someData': 'data'}
        }]

        self.assertEqual(results, expected)

    def test_incremental(self):
        source = {
            'access_token': 'someToken',
            'lastTimeSucceed': '2016-09-21T10:23:42.819Z',
            'forms': [{'value': 'abc', 'name': 'Test Survey'}]
        }

        results = generate_form_results(1)
        requests.get = MagicMock(return_value=MockResponse(results, 200))

        stream = Typeform(source, OPTIONS)
        stream.read()

        # the focus here is on the 'since' query param that indicates
        # we're pulling data after a specific date
        url = '{}/forms/{}/responses'.format(
            BASE_URL,
            source['forms'][0].get('value')
        )
        expected_params = {
            'sort': 'landed_at,desc',
            'completed': 1,
            'since': '2016-09-20T21:23:42',
            'page_size': 1000
        }
        requests.get.assert_called_with(
            url,
            headers=HEADERS,
            params=expected_params
        )

    def test_pagination(self):
        source = {
            'access_token': 'someToken',
            'forms': [{'value': 'abc', 'name': 'Test Survey'}]
        }

        res1, res2 = generate_form_results(1000), generate_form_results(0)
        requests.get = MagicMock(side_effect=[
            MockResponse(res1, 200),
            MockResponse(res2, 200)
        ])

        stream = Typeform(source, OPTIONS)
        stream.read()  # 1st page
        stream.read()  # 2nd page
        self.assertIsNone(stream.read())  # we're done

        # it should make 1 requests.
        self.assertEqual(requests.get.call_count, 2)

        # test that it constructed the correct url
        url = '{}/forms/{}/responses'.format(
            BASE_URL,
            source['forms'][0].get('value')
        )
        expected_params = {
            'sort': 'landed_at,desc',
            'completed': 1,
            'page_size': 1000,
            'before': 999
        }
        requests.get.assert_called_with(
            url,
            headers=HEADERS,
            params=expected_params
        )

    def test_iterate_forms(self):
        source = {
            'access_token': 'TypefromToken',
            'forms': [
                {'value': 'abc', 'name': 'Test Survey'},
                {'value': 'edf', 'name': 'Test Survey'}
            ]
        }

        res1 = res3 = generate_form_results(1)
        res2 = res4 = generate_form_results(0)
        requests.get = MagicMock(side_effect=[
            MockResponse(res1, 200),
            MockResponse(res2, 200),
            MockResponse(res3, 200),
            MockResponse(res4, 200),
        ])

        stream = Typeform(source, OPTIONS)
        d = stream.read()
        while d is not None:
            d = stream.read()
        self.assertEqual(requests.get.call_count, 2)

    def test_read_with_errors(self):

        response = MockResponse([], 500)
        requests.get = MagicMock(return_value=response)

        source = {
            'key': 'TypefromAPIKey',
            'forms': [{'value': 'someid', 'name': 'Test Survey'}]
        }
        stream = Typeform(source, OPTIONS)

        self.assertRaises(requests.exceptions.RequestException, stream.read)
        self.assertEqual(requests.get.call_count, 5)

    def test_get_forms(self):
        forms = [{'id': 1, 'title': 'Form #1'}]
        response = MockResponse({'items': forms}, 200)
        requests.get = MagicMock(return_value=response)
        source = {
            'key': 'TypefromAPIKey',
            'forms': [{'value': 'someid', 'name': 'Test Survey'}]
        }
        stream = Typeform(source, OPTIONS)
        expected = map(lambda f: dict(name=f.get('title'),
                                      value=f.get('id')), forms)
        self.assertEqual(stream.get_forms(), expected)

    def test_form_type(self):
        source = {
            'access_token': 'someToken',
            'forms': [{'value': 'abc', 'name': 'Test Survey'}],
            '__formTypes': 'all'
        }

        res1 = generate_form_results_completed_and_not(10)
        requests.get = MagicMock(side_effect=[MockResponse(res1, 200)])

        stream = Typeform(source, OPTIONS)
        stream.read()

        url = '{}/forms/{}/responses'.format(
            BASE_URL,
            source['forms'][0].get('value')
        )

        expected_params = {
            'sort': 'landed_at,desc',
            'page_size': 1000
        }

        requests.get.assert_called_with(
            url,
            headers=HEADERS,
            params=expected_params
        )

    def test_default_form_type(self):
        source = {
            'access_token': 'someToken',
            'forms': [{'value': 'abc', 'name': 'Test Survey'}]
        }

        res1 = generate_form_results_completed_and_not(10)
        requests.get = MagicMock(side_effect=[MockResponse(res1, 200)])

        stream = Typeform(source, OPTIONS)
        stream.read()

        url = '{}/forms/{}/responses'.format(
            BASE_URL,
            source['forms'][0].get('value')
        )

        expected_params = {
            'sort': 'landed_at,desc',
            'page_size': 1000,
            'completed': 1
        }

        requests.get.assert_called_with(
            url,
            headers=HEADERS,
            params=expected_params
        )

    def test_not_completed_form_type(self):
        source = {
            'access_token': 'someToken',
            'forms': [{'value': 'abc', 'name': 'Test Survey'}],
            '__formTypes': 'not_completed'
        }

        res1 = generate_form_results_completed_and_not(10)
        requests.get = MagicMock(side_effect=[MockResponse(res1, 200)])

        stream = Typeform(source, OPTIONS)
        stream.read()

        url = '{}/forms/{}/responses'.format(
            BASE_URL,
            source['forms'][0].get('value')
        )

        expected_params = {
            'sort': 'landed_at,desc',
            'page_size': 1000,
            'completed': 0
        }

        requests.get.assert_called_with(
            url,
            headers=HEADERS,
            params=expected_params
        )


def generate_form_results(size):
    responses = [{
        'token': x,
        'metadata': {
            "someData": "data",
        },
        'answers': [
            {
                "field": {
                    "id": "quetion1_id",
                    "type": "short_text",
                },
                "type": "text",
                "text": "some_answer1"
            },
            {
                "field": {
                    "id": "quetion2_id",
                    "type": "multiple_choice",
                },
                'type': 'choice',
                'choice': {
                    "label": 'Agree'
                }
            }
        ]
    }
        for x in range(0, size)
    ]

    return {
        'total_items': size,
        'page_count': size,
        'items': responses,
    }


def generate_form_results_not_completed(size):
    responses = [{
        'token': x,
        'metadata': {
            "someData": "data",
        },
        'answers': []
    }
        for x in range(0, size)
    ]

    return {
        'total_items': size,
        'page_count': size,
        'items': responses,
    }


def generate_form_results_completed_and_not(size):
    not_completed_responses = [{
        'token': x,
        'metadata': {
            "someData": "data",
        },
        'answers': []
    }
        for x in range(0, size)
    ]

    completed_responses = [{
        'token': x,
        'metadata': {
            "someData": "data",
        },
        'answers': [
            {
                "field": {
                    "id": "quetion1_id",
                    "type": "short_text",
                },
                "type": "text",
                "text": "some_answer1"
            },
            {
                "field": {
                    "id": "quetion2_id",
                    "type": "multiple_choice",
                },
                'type': 'choice',
                'choice': {
                    "label": 'Agree'
                }
            }
        ]
    }
        for x in range(0, size)
    ]

    responses = not_completed_responses + completed_responses

    return {
        'total_items': size,
        'page_count': size,
        'items': responses,
    }


if __name__ == '__main__':
    unittest.main()
