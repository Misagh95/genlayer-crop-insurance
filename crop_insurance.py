# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json

class PolicyData:
    owner: Address
    crop: str
    location: str
    lat: float
    lon: float
    coverage: u256
    premium: u256
    start_ts: u256
    end_ts: u256
    min_rain_mm: float
    max_temp_c: float
    claimed: bool
    paid: bool

class CropInsurance(gl.Contract):
    policies: TreeMap[u256, PolicyData]
    user_policies: TreeMap[Address, DynArray[u256]]
    next_id: u256

    def __init__(self):
        self.next_id = u256(1)

    @gl.public.write.payable
    def buy_policy(
        self,
        crop: str,
        location: str,
        lat: float,
        lon: float,
        coverage: u256,
        start_ts: u256,
        end_ts: u256,
        min_rain_mm: float,
        max_temp_c: float
    ):
        if gl.value_of_transaction() < coverage // u256(10):
            raise UserError("premium must be at least 10% of coverage")

        # TODO: add validation for lat/lon range
        if start_ts >= end_ts:
            raise UserError("start must be before end")

        pid = self.next_id
        p = PolicyData()
        p.owner = gl.caller_address
        p.crop = crop
        p.location = location
        p.lat = lat
        p.lon = lon
        p.coverage = coverage
        p.premium = gl.value_of_transaction()
        p.start_ts = start_ts
        p.end_ts = end_ts
        p.min_rain_mm = min_rain_mm
        p.max_temp_c = max_temp_c
        p.claimed = False
        p.paid = False

        self.policies[pid] = p

        existing = self.user_policies.get(gl.caller_address)
        if existing is None:
            existing = DynArray[u256]()
        existing.append(pid)
        self.user_policies[gl.caller_address] = existing

        self.next_id += u256(1)

    @gl.public.write
    def claim(self, policy_id: u256):
        p = self.policies.get(policy_id)
        if p is None:
            raise UserError("policy not found")
        if p.owner != gl.caller_address:
            raise UserError("not your policy")
        if p.claimed:
            raise UserError("already claimed")
        if p.paid:
            raise UserError("already paid out")

        p.claimed = True
        self.policies[policy_id] = p

        payout = self._assess(policy_id)
        if payout > u256(0):
            p.paid = True
            self.policies[policy_id] = p
            gl.transfer(p.owner, payout)

    @gl.public.view
    def get_policy(self, policy_id: u256) -> dict:
        p = self.policies.get(policy_id)
        if p is None:
            return {"error": "not found"}
        return {
            "owner": str(p.owner),
            "crop": p.crop,
            "location": p.location,
            "coverage": str(p.coverage),
            "premium": str(p.premium),
            "claimed": p.claimed,
            "paid": p.paid
        }

    @gl.public.view
    def my_policies(self) -> DynArray[u256]:
        arr = self.user_policies.get(gl.caller_address)
        if arr is None:
            return DynArray[u256]()
        return arr

    # ------------------------------------------------------------------
    # two-phase consensus:
    # 1. fetch weather from Open-Meteo (validators independently verify)
    # 2. LLM damage assessment with prompt_comparative
    # ------------------------------------------------------------------
    def _assess(self, policy_id: u256) -> u256:
        p_copy = gl.storage.copy_to_memory(self.policies[policy_id])

        # -------- stage 1: weather data with consensus --------
        def fetch_weather():
            url = (f"https://archive-api.open-meteo.com/v1/archive"
                   f"?latitude={p_copy.lat}&longitude={p_copy.lon}"
                   f"&daily=precipitation_sum,temperature_2m_max"
                   f"&start_date={p_copy.start_ts}&end_date={p_copy.end_ts}"
                   f"&timezone=auto")
            resp = gl.nondet.web.get(url)
            return resp.body.decode("utf-8")

        def validate_weather(leader_res):
            if not isinstance(leader_res, gl.vm.Return):
                return False
            try:
                mine = fetch_weather()
                ld = json.loads(leader_res.calldata)
                md = json.loads(mine)
                # check both responses have the expected structure
                if "daily" not in ld or "daily" not in md:
                    return False
                return True
            except Exception:
                return False

        weather_str = gl.vm.run_nondet_unsafe(fetch_weather, validate_weather)
        if weather_str is None:
            return u256(0)

        # -------- stage 2: LLM damage assessment با consensus --------
        prompt = (
            f"You are a parametric crop insurance adjuster.\n"
            f"Crop: {p_copy.crop}\n"
            f"Location: {p_copy.location}\n"
            f"Period: {p_copy.start_ts} to {p_copy.end_ts}\n"
            f"Min rainfall threshold: {p_copy.min_rain_mm}mm (below = drought risk)\n"
            f"Max temp threshold: {p_copy.max_temp_c}C (above = heat stress)\n"
            f"Weather data: {weather_str}\n"
            f"Return ONLY valid JSON (no markdown): "
            f'{{"drought":bool,"heat_damage":bool,"payout_ratio":0.0-1.0}}'
        )

        def evaluate():
            return gl.nondet.exec_prompt(prompt)

        # all validators run the LLM eval, prompt_comparative checks
        # whether outputs are semantically equivalent
        decision = gl.eq_principle.prompt_comparative(
            evaluate,
            "Validators must agree on the payout_ratio within reasonable tolerance"
        )

        # -------- stage 3: parse consensus result & pay --------
        try:
            raw = str(decision).strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
            ratio = max(0.0, min(1.0, float(data.get("payout_ratio", 0.0))))
            payout = int(float(p_copy.coverage) * ratio)
            print(f"[assess] policy {policy_id}: ratio={ratio}, payout={payout}")
            return u256(payout)
        except Exception as e:
            print(f"[assess] parse failed: {e}, got: {decision}")
            return u256(0)
