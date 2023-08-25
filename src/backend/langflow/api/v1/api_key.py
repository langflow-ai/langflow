from fastapi import APIRouter


router = APIRouter(tags=["APIKey"])


@router.get("/api_key/{user_id}")
def get_api_key(user_id: str):
    return {
        "total_count": 3,
        "user_id": user_id,
        "api_keys": [
            {
                "id": "4425707e-cce4-4d1b-a54e-bd2632064657",
                "api_key": "lf-...abcd",
                "name": "my api_key name - 01",
                "created_at": "2023-08-15T19:28:40.019613",
                "last_used_at": "2023-08-16T18:38:20.875210",
            },
            {
                "id": "6fb7282b-9f2e-4efe-9bda-0c3d8f899473",
                "api_key": "lf-...abcd",
                "name": "my api_key name - 02",
                "created_at": "2023-08-15T19:41:30.077942",
                "last_used_at": "2023-08-15T19:45:32.067899",
            },
            {
                "id": "c55f3b32-4920-42b6-a5cd-698b4251806e",
                "api_key": "lf-...abcd",
                "name": "my api_key name - 03",
                "created_at": "2023-08-15T20:29:40.577808",
                "last_used_at": "2023-08-15T20:29:40.577816",
            },
        ],
    }


@router.post("/api_key/{user_id}")
def create_api_key(user_id: str):
    return {
        "user_id": user_id,
        "name": "my api-key 01",
        "api_key": "lf-eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YTBmODM1ZS0yMTQxLTQ2YWItYmQ4NS0yMWEzMjQ1MTE2ZDAiLCJleHAiOjE2OTIyMTUwMTN9.c_s0ZPRtjSI9yUrhi8ACIwyXf0feRLYfaeIZEbRVKQg",  # noqa
    }


@router.delete("/api_key/{api_key_id}")
def delete_api_key(api_key_id: str):
    return {"detail": "API Key deleted"}
