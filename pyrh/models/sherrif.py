import time

import requests


class Sherrif:
    def __init__(self, session: requests.Session):
        self.session = session

    def request_post(
        self, url, payload=None, timeout=16, json=False, jsonify_data=True
    ):
        """For a given url and payload, makes a post request and returns the response. Allows for responses other than 200.

        :param url: The url to send a post request to.
        :type url: str
        :param payload: Dictionary of parameters to pass to the url as url/?key1=value1&key2=value2.
        :type payload: Optional[dict]
        :param timeout: The time for the post to wait for a response. Should be slightly greater than multiples of 3.
        :type timeout: Optional[int]
        :param json: This will set the 'content-type' parameter of the session header to 'application/json'
        :type json: bool
        :param jsonify_data: If this is true, will return requests.post().json(), otherwise will return response from requests.post().
        :type jsonify_data: bool
        :returns: Returns the data from the post request.

        """
        data = None
        res = None
        try:
            if json:
                self.session.headers["Content-Type"] = "application/json"
                res = self.session.post(url, json=payload, timeout=timeout)
                self.session.headers[
                    "Content-Type"
                ] = "application/x-www-form-urlencoded; charset=utf-8"
            else:
                res = self.session.post(url, data=payload, timeout=timeout)
            if res.status_code not in [
                200,
                201,
                202,
                204,
                301,
                302,
                303,
                304,
                307,
                400,
                401,
                402,
                403,
            ]:
                raise Exception("Received " + str(res.status_code))
            data = res.json()
        except Exception as message:
            print("Error in request_post: {0}".format(message))
        if jsonify_data:
            return data
        else:
            return res

    def request_get(self, url, dataType="regular", payload=None, jsonify_data=True):
        """For a given url and payload, makes a get request and returns the data.

        :param url: The url to send a get request to.
        :type url: str
        :param dataType: Determines how to filter the data. 'regular' returns the unfiltered data. \
        'results' will return data['results']. 'pagination' will return data['results'] and append it with any \
        data that is in data['next']. 'indexzero' will return data['results'][0].
        :type dataType: Optional[str]
        :param payload: Dictionary of parameters to pass to the url. Will append the requests url as url/?key1=value1&key2=value2.
        :type payload: Optional[dict]
        :param jsonify_data: If this is true, will return requests.post().json(), otherwise will return response from requests.post().
        :type jsonify_data: bool
        :returns: Returns the data from the get request. If jsonify_data=True and requests returns an http code other than <200> \
        then either '[None]' or 'None' will be returned based on what the dataType parameter was set as.

        """
        if dataType == "results" or dataType == "pagination":
            data = [None]
        else:
            data = None
        res = None
        if jsonify_data:
            try:
                res = self.session.get(url, params=payload)
                res.raise_for_status()
                data = res.json()
            except (requests.exceptions.HTTPError, AttributeError) as message:
                print(message)
                return data
        else:
            res = self.session.get(url, params=payload)
            return res
        # Only continue to filter data if jsonify_data=True, and Session.get returned status code <200>.
        if dataType == "results":
            try:
                data = data["results"]
            except KeyError as message:
                print(
                    "{0} is not a key in the dictionary".format(message),
                    file=get_output(),
                )
                return [None]
        elif dataType == "pagination":
            counter = 2
            nextData = data
            try:
                data = data["results"]
            except KeyError as message:
                print(
                    "{0} is not a key in the dictionary".format(message),
                    file=get_output(),
                )
                return [None]

            if nextData["next"]:
                print("Found Additional pages.", file=get_output())
            while nextData["next"]:
                try:
                    res = SESSION.get(nextData["next"])
                    res.raise_for_status()
                    nextData = res.json()
                except:
                    print(
                        "Additional pages exist but could not be loaded.",
                        file=get_output(),
                    )
                    return data
                print("Loading page " + str(counter) + " ...", file=get_output())
                counter += 1
                for item in nextData["results"]:
                    data.append(item)
        elif dataType == "indexzero":
            try:
                data = data["results"][0]
            except KeyError as message:
                print(
                    "{0} is not a key in the dictionary".format(message),
                    file=get_output(),
                )
                return None
            except IndexError as message:
                return None

        return data

    def validate_sherrif_id(self, device_token: str, workflow_id: str):
        """Handles Robinhood's verification workflow, including email, SMS, and app-based approvals."""
        print("Starting verification process...")
        pathfinder_url = "https://api.robinhood.com/pathfinder/user_machine/"
        machine_payload = {
            "device_id": device_token,
            "flow": "suv",
            "input": {"workflow_id": workflow_id},
        }
        machine_data = self.request_post(
            url=pathfinder_url, payload=machine_payload, json=True
        )

        machine_id = machine_data["id"]
        inquiries_url = (
            f"https://api.robinhood.com/pathfinder/inquiries/{machine_id}/user_view/"
        )

        start_time = time.time()

        while time.time() - start_time < 120:  # 2-minute timeout
            time.sleep(5)
            inquiries_response = self.request_get(inquiries_url)

            if not inquiries_response:  # Handle case where response is None
                print("Error: No response from Robinhood API. Retrying...")
                continue

            if (
                "context" in inquiries_response
                and "sheriff_challenge" in inquiries_response["context"]
            ):
                challenge = inquiries_response["context"]["sheriff_challenge"]
                challenge_type = challenge["type"]
                challenge_status = challenge["status"]
                challenge_id = challenge["id"]
                if challenge_type == "prompt":
                    print("Check robinhood app for device approvals method...")
                    prompt_url = f"https://api.robinhood.com/push/{challenge_id}/get_prompts_status/"
                    while True:
                        time.sleep(5)
                        prompt_challenge_status = self.request_get(url=prompt_url)
                        if prompt_challenge_status["challenge_status"] == "validated":
                            break
                    break

                if challenge_status == "validated":
                    print("Verification successful!")
                    break  # Stop polling once verification is complete

                if challenge_type in ["sms", "email"] and challenge_status == "issued":
                    user_code = input(
                        f"Enter the {challenge_type} verification code sent to your device: "
                    )
                    challenge_url = (
                        f"https://api.robinhood.com/challenge/{challenge_id}/respond/"
                    )
                    challenge_payload = {"response": user_code}
                    challenge_response = self.request_post(
                        url=challenge_url, payload=challenge_payload
                    )

                    if challenge_response.get("status") == "validated":
                        break

        # **Now poll the workflow status to confirm final approval**
        inquiries_url = (
            f"https://api.robinhood.com/pathfinder/inquiries/{machine_id}/user_view/"
        )

        retry_attempts = 5  # Allow up to 5 retries in case of 500 errors
        while time.time() - start_time < 120:  # 2-minute timeout
            try:
                inquiries_payload = {
                    "sequence": 0,
                    "user_input": {"status": "continue"},
                }
                inquiries_response = self.request_post(
                    url=inquiries_url, payload=inquiries_payload, json=True
                )
                if (
                    "type_context" in inquiries_response
                    and inquiries_response["type_context"]["result"]
                    == "workflow_status_approved"
                ):
                    print("Verification successful!")
                    return
                else:
                    time.sleep(
                        5
                    )  # **Increase delay between requests to prevent rate limits**
            except requests.exceptions.RequestException as e:
                time.sleep(5)
                print(f"API request failed: {e}")
                retry_attempts -= 1
                if retry_attempts == 0:
                    raise TimeoutError(
                        "Max retries reached. Assuming login approved and proceeding."
                    )
                print("Retrying workflow status check...")
                continue

            if not inquiries_response:  # Handle None response
                time.sleep(5)
                print("Error: No response from Robinhood API. Retrying...")
                retry_attempts -= 1
                if retry_attempts == 0:
                    raise TimeoutError(
                        "Max retries reached. Assuming login approved and proceeding."
                    )
                continue

            workflow_status = inquiries_response.get("verification_workflow", {}).get(
                "workflow_status"
            )

            if workflow_status == "workflow_status_approved":
                print("Workflow status approved! Proceeding with login...")
                return
            elif workflow_status == "workflow_status_internal_pending":
                print("Still waiting for Robinhood to finalize login approval...")
            else:
                retry_attempts -= 1
                if retry_attempts == 0:
                    raise TimeoutError(
                        "Max retries reached. Assuming login approved and proceeding."
                    )

        raise TimeoutError(
            "Timeout reached. Assuming login is approved and proceeding."
        )
