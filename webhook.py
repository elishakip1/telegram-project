from fastapi import FastAPI, Request
from supabase import create_client
import yaml, uvicorn

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)
supabase = create_client(config['supabase']['url'], config['supabase']['key'])
app = FastAPI()

@app.post("/dv-webhook")
async def dv_webhook(request: Request):
    data = await request.json()
    if data.get('status') == "confirmed":
        uid = data.get('store_external_id')
        amt = float(data.get('amount', 0))
        user = supabase.table("users").select("balance").eq("user_id", uid).single().execute().data
        supabase.table("users").update({"balance": float(user['balance']) + amt}).eq("user_id", uid).execute()
        return {"status": "success"}
    return {"status": "ignored"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)