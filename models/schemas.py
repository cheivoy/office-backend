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
    from_date: str = ""
    to_date:   str = ""
    amount:    Optional[float] = None
    # Legacy fields kept for backward compatibility with old saved data
    date:      Optional[str] = None
    tstart:    Optional[str] = None
    tend:      Optional[str] = None
    hours:     Optional[float] = None
    ns_amount: Optional[float] = None

class NsEntry(BaseModel):
    date:   str
    tstart: str = ""
    tend:   str = ""
    hours:  Optional[float] = None
    amount: Optional[float] = None

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
    from_date: str = ""          # start date e.g. "2026-05-04"
    to_date:   str = ""          # end date (same as from_date for single day)
    tstart:    Optional[str] = None   # start time "09:00"
    tend:      Optional[str] = None   # end time "18:00"
    hours:     Optional[str] = None   # manual override if no time range
    type:      str = "sick leave"
    reason:    Optional[str] = None   # used when type == "other"
    # Legacy field - kept for backward compat
    dates:     Optional[str] = None

class SubmitPayload(BaseModel):
    emp_name:    str
    emp_en:      str
    work_days:   Optional[float] = None
    ess:         list[EssEntry] = []
    ns:          list[NsEntry] = []
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