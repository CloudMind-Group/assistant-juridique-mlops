from locust import HttpUser, task, between

class ChatUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        response = self.client.post("/login", data={
            "username": "user_test",
            "password": "test1234",
        })
        token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    @task
    def ask_question(self):
        self.client.post(
            "/chat?question=Quelle règle de droit est décrite ?",
            headers=self.headers,
        )