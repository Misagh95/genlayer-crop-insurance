# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from genlayer import allow_storage
from dataclasses import dataclass
import json


@allow_storage
@dataclass
class PolicyData:
    owner: Address
    lat: float
    lon: float
    coverage: u256
    start_ts: u256
    end_ts: u256
    min_rain_mm: float
    max_temp_c: float
    claimed: bool
    paid: bool


class CropInsurance(gl.Contract):
    policies: TreeMap[u256, PolicyData]
    policy_info: TreeMap[u256, str]
    user_policies: TreeMap[Address, DynArray[u256]]
    next_id: u256

    def __init__(self):
        self.next_id = u256(1)

    @gl.public.write
    def buy_policy(
        self,
        crop: str,
        place: str,
        lat: float,
        lon: float,
        coverage: u256,
        start_ts: u256,
        end_ts: u256,
        min_rain_mm: float,
        max_temp_c: float,
    ):
        pid = self.next_id
        p = PolicyData(
            owner=gl.message.sender_address,
            lat=lat, lon=lon,
            coverage=coverage,
            start_ts=start_ts, end_ts=end_ts,
            min_rain_mm=min_rain_mm, max_temp_c=max_temp_c,
            claimed=False, paid=False,
        )
        self.policies[pid] = p
        self.policy_info[pid] = crop + "|" + place

        existing = self.user_policies.get(gl.message.sender_address)
        if existing is None:
            existing = DynArray[u256]()
        existing.append(pid)
        self.user_policies[gl.message.sender_address] = existing
        self.next_id += u256(1)

    @gl.public.write
    def claim(self, policy_id: u256):
        p = self.policies.get(policy_id)
        if p is None:
            raise UserError("not found")
        if p.owner != gl.message.sender_address:
            raise UserError("not your policy")
        if p.claimed:
            raise UserError("already claimed")

        p.claimed = True
        self.policies[policy_id] = p
        payout = self._assess(policy_id)
        if payout > u256(0):
            p.paid = True
            self.policies[policy_id] = p

    @gl.public.view
    def get_policy(self, policy_id: u256) -> str:
        p = self.policies.get(policy_id)
        if p is None:
            return "not found"
        info = self.policy_info.get(policy_id, "")
        return (f"info={info}|cov={p.coverage}|"
                f"clm={p.claimed}|paid={p.paid}")

    @gl.public.view
    def my_policies(self) -> str:
        arr = self.user_policies.get(gl.message.sender_address)
        if arr is None:
            return "empty"
        return ",".join(str(int(x)) for x in arr)

    def _assess(self, policy_id: u256) -> u256:
        p_copy = gl.storage.copy_to_memory(self.policies[policy_id])
        info = gl.storage.copy_to_memory(self.policy_info[policy_id])
        parts = info.split("|")
        crop_name = parts[0] if len(parts) > 0 else ""
        place_name = parts[1] if len(parts) > 1 else ""

        def fetch_weather():
            url = (
                f"https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={p_copy.lat}&longitude={p_copy.lon}"
                f"&daily=precipitation_sum,temperature_2m_max"
                f"&start_date={p_copy.start_ts}&end_date={p_copy.end_ts}"
                f"&timezone=auto"
            )
            resp = gl.nondet.web.get(url)
            return resp.body.decode("utf-8")

        def validate_weather(leader_res):
            if not isinstance(leader_res, gl.vm.Return):
                return False
            try:
                mine = fetch_weather()
                ld = json.loads(leader_res.calldata)
                md = json.loads(mine)
                return "daily" in ld and "daily" in md
            except Exception:
                return False

        weather_str = gl.vm.run_nondet_unsafe(fetch_weather, validate_weather)
        if weather_str is None:
            return u256(0)

        prompt = (
            f"You are a crop insurance adjuster.\n"
            f"Crop: {crop_name}\nLocation: {place_name}\n"
            f"Period: {p_copy.start_ts} to {p_copy.end_ts}\n"
            f"Min rain: {p_copy.min_rain_mm}mm\n"
            f"Max temp: {p_copy.max_temp_c}C\n"
            f"Weather: {weather_str}\n"
            f'Return JSON: {{"drought":bool,"heat_damage":bool,"payout_ratio":0.0-1.0}}'
        )

        def evaluate():
            return gl.nondet.exec_prompt(prompt)

        decision = gl.eq_principle.prompt_comparative(
            evaluate, "Validators must agree on payout_ratio"
        )

        try:
            raw = str(decision).strip()
            raw = (raw.removeprefix("```json")
                      .removeprefix("```")
                      .removesuffix("```")
                      .strip())
            data = json.loads(raw)
            ratio = max(0.0, min(1.0, float(data.get("payout_ratio", 0.0))))
            return u256(int(float(p_copy.coverage) * ratio))
        except Exception:
            return u256(0)
