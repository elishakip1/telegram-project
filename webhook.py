from fastapi import FastAPI, Request
import uvicorn

from app.services.db import get_supabase

supabase = get_supabase()
app = FastAPI()


@app.post("/dv-webhook")
async def dv_webhook(request: Request):
    data = await request.json()
    if data.get("status") != "confirmed":
        return {"status": "ignored"}

    uid = data.get("store_external_id")
    if uid is None:
        return {"status": "ignored", "reason": "missing store_external_id"}

    amount = float(data.get("amount", 0))
    user_resp = supabase.table("users").select("balance").eq("user_id", int(uid)).single().execute()
    user = user_resp.data
    if not user:
        return {"status": "ignored", "reason": "user not found"}

    new_balance = float(user.get("balance", 0)) + amount
    supabase.table("users").update({"balance": new_balance}).eq("user_id", int(uid)).execute()
    return {"status": "success"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
