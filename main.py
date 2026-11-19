import json
import urllib.error
import urllib.request

from app import app

BASE_URL = "http://127.0.0.1:5000"

def example_request(method, endpoint, data=None):
    url = f"{BASE_URL}{endpoint}"

    headers = {
        "Content-Type": "application/json"
    }

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = response.read().decode("utf-8")

            print(f"\n{method} {endpoint}")
            print(f"Status: {response.status}")
            print(json.dumps(json.loads(result), indent=4))

    except urllib.error.HTTPError as error:
        result = error.read().decode("utf-8")

        print(f"\n{method} {endpoint}")
        print(f"Status: {error.code}")
        print(result)

    except urllib.error.URLError as error:
        print(f"Could not connect to API: {error.reason}")


def run_examples():
    example_request("GET", "/health")
    example_request("GET", "/api/majors")

    example_request(
        "POST",
        "/api/majors",
        {
            "MajorName": "Computer Science"
        }
    )

    example_request(
        "GET",
        "/api/players?page=1&per_page=10"
    )

    example_request(
        "POST",
        "/api/players",
        {
            "FirstName": "John",
            "LastName": "Smith",
            "StocktonID": "S123456",
            "DateOfBirth": "2004-05-15",
            "GraduationDateExpected": "2027-05-20"
        }
    )

    example_request("GET", "/api/seasons")


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )