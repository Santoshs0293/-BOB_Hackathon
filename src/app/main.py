from fastapi import FastAPI
from .routers import auth, transactions, investigators
from .assistant import router as assistant_router

app = FastAPI(title="CAI Powered UEBA (MongoDB + Feedback Loop)")

# Routers
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(investigators.router)
app.include_router(assistant_router)

@app.get("/")
def root():
    return {"msg": "CAI UEBA backend running with MongoDB"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app.main:app", host="0.0.0.0", port=8000, reload=True)
