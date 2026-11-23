from pydantic import BaseModel

class EventRegistrationCreate(BaseModel):
    event_id: int
    customer_id: int