from pydantic import BaseModel, Field
from typing import Optional

class Attachment(BaseModel):
    filename:     str
    content_type: str
    data:         str

class MessageEnvelope(BaseModel):
    uid:            str
    subject:        Optional[str] = ''
    from_:          Optional[str] = Field(None, alias="from")
    to:             Optional[str] = None
    date:           Optional[str] = None
    text_body:      Optional[str] = ''
    html_body:      Optional[str] = ''
    attachments:    list[Attachment] = []

    class Config:
        populate_by_name = True
