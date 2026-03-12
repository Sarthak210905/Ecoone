from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional

app = FastAPI(title="Smart Solar Estimation API 🔆")

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VENDORS = {
    "Default": ["Tata Power Solar", "Adani Solar", "Waaree Energies"],
    "Premium": ["Loom Solar", "Vikram Solar"],
    "Budget": ["RenewSys", "Servotech Power"]
}

THRESHOLD_AREAS = {
    "Default": 10,
    "Chhattisgarh": 8,
    "Mumbai": 12,
    "Madhya Pradesh": 10,
    "Uttar Pradesh": 10,
}

def estimate_solar_requirements_consistent(
    length_m: float,
    breadth_m: float,
    vendor_type: str = "Default",
    state: str = "Default",
    panel_area_m2: float = 1.7,
    panel_watt: int = 400,
    usable_ratio: float = 0.75,
    cost_per_kw: float = 55000.0
):
    total_area = length_m * breadth_m
    threshold = THRESHOLD_AREAS.get(state, 10)
    usable_area = round(total_area * usable_ratio, 2)
    num_panels = int(usable_area // panel_area_m2)
    system_capacity_kw = round((num_panels * panel_watt) / 1000, 2)
    estimated_cost_inr = round(system_capacity_kw * cost_per_kw, 2)
    feasible = total_area >= threshold
    
    message = (
        f"✅ Suitable area for solar panel installation ({num_panels} panels can fit, ~{system_capacity_kw} kW)"
        if feasible
        else f"⚠️ Area too small for solar installation (Minimum {threshold} m² required)"
    )
    
    vendors = VENDORS.get(vendor_type, VENDORS["Default"]) if feasible else []
    
    return {
        "feasible": feasible,
        "state": state,
        "length_m": length_m,
        "breadth_m": breadth_m,
        "total_area_m2": round(total_area, 2),
        "usable_area_m2": usable_area,
        "panel_area_m2": panel_area_m2,
        "panel_watt": panel_watt,
        "estimated_no_of_panels": num_panels,
        "estimated_system_kw": system_capacity_kw,
        "required_minimum_area_m2": threshold,
        "estimated_cost_inr": estimated_cost_inr,
        "message": message,
        "recommended_vendors": vendors
    }

def estimate_from_units(monthly_units: float, state: str = "Default", vendor_type: str = "Default"):
    three_months_kwh = monthly_units * 3
    daily_load_kwh = round(monthly_units / 30, 2)
    required_capacity_kw = round(daily_load_kwh / 4, 2)
    estimated_cost_inr = round(required_capacity_kw * 55000, 2)
    vendors = VENDORS.get(vendor_type, VENDORS["Default"])
    
    return {
        "state": state,
        "monthly_units": monthly_units,
        "three_month_consumption_kwh": three_months_kwh,
        "average_daily_load_kwh": daily_load_kwh,
        "required_solar_capacity_kw": required_capacity_kw,
        "estimated_cost_inr": estimated_cost_inr,
        "message": f"To cover your {monthly_units} units/month, you need approx. a {required_capacity_kw} kW solar system.",
        "recommended_vendors": vendors
    }

@app.post("/solar/smart")
async def smart_estimator(
    length_m: Optional[float] = Form(None),
    breadth_m: Optional[float] = Form(None),
    monthly_units: Optional[float] = Form(None),
    state: str = Form("Default"),
    vendor_type: str = Form("Default"),
    photo: Optional[UploadFile] = File(None)
):
    result = {"mode_used": None}
    
    if length_m and breadth_m:
        area_result = estimate_solar_requirements_consistent(length_m, breadth_m, vendor_type, state)
        result["manual_area_result"] = area_result
        result["mode_used"] = "Area-based"
    
    if monthly_units:
        unit_result = estimate_from_units(monthly_units, state, vendor_type)
        result["consumption_result"] = unit_result
        result["mode_used"] = "Consumption-based" if not result["mode_used"] else "Both"
    
    if not length_m and not breadth_m and not monthly_units:
        return JSONResponse(
            content={"error": "Please provide either (length & breadth) or monthly_units."},
            status_code=400
        )
    
    if photo:
        result["photo_uploaded"] = photo.filename
    
    return JSONResponse(content=result)

@app.post("/solar/manual")
async def manual_estimator(
    length_m: float = Form(...),
    breadth_m: float = Form(...),
    state: str = Form("Default"),
    vendor_type: str = Form("Default")
):
    result = estimate_solar_requirements_consistent(length_m, breadth_m, vendor_type, state)
    return JSONResponse(content=result)

@app.get("/")
async def root():
    return {"message": "Smart Solar Estimation API is running! 🔆"}
