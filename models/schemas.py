from pydantic import BaseModel
from typing import Optional

class Person(BaseModel):
    id:    Optional[int] = None
    proj:  str
    unit:  str = ""
    pm:    str = ""
    cn:    str = ""
    en:    str

class EssEntry(BaseModel):
    date:      str
    tstart:    str
    tend:      str
    hours:     Optional[float] = None
    amount:    Optional[float] = None
    ns_amount: Optional[float] = None

class OtEntry(BaseModel):
    date:   str
    tstart: str
    tend:   str
    hours:  Optional[float] = None
    amount: Optional[float] = None

class TaEntry(BaseModel):
    from_date: str
    to_date:   str
    amount:    Optional[float] = None

class LeaveEntry(BaseModel):
    dates:  str           # space-separated e.g. "0504 0514"
    type:   str = "sick leave"
    hours:  Optional[str] = None
    reason: Optional[str] = None  # used when type == "other"

class SubmitPayload(BaseModel):
    emp_name:    str
    emp_en:      str
    work_days:   Optional[float] = None
    ess:         list[EssEntry] = []
    ot:          list[OtEntry]  = []
    ta:          list[TaEntry]  = []
    leave:       list[LeaveEntry] = []
    write_target: str = "cht_nokia"   # cht_nokia | cht_dk | wipro_snda

class WiproEntry(BaseModel):
    emp_name:   str
    ess_amount:   Optional[float] = None
    shift_amount: Optional[float] = None
    ot:           list[OtEntry]  = []
    travel_amount:Optional[float] = None
