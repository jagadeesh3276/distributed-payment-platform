from locust import HttpUser, task, between
import uuid
class PaymentUser(HttpUser):
    wait_time = between(0.1, 0.8)
    @task(5)
    def health(self):
        self.client.get("/health")
    @task(2)
    def create_account_and_deposit(self):
        suffix = uuid.uuid4().hex[:12]
        account = f"LOAD{suffix}"
        response = self.client.post("/accounts", json={"account_number":account,"owner_id":f"USER{suffix}","currency":"INR"})
        if response.status_code == 201:
            self.client.post(f"/accounts/{account}/deposits", headers={"Idempotency-Key":f"load-{suffix}"}, json={"amount":"100.00"})
