from pydantic import BaseModel


class ProcedureParameters(BaseModel):
    consumer_number: int
    start_date: str
    end_date: str
    commodity_name: str


class ProcessMessageRequest(BaseModel):
    procedure: str
    parameters: ProcedureParameters
