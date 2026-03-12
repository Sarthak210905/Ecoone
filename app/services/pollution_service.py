import random
from typing import Dict, Any
from app.database.database import get_pollution_data_collection
from datetime import datetime, timedelta


class PollutionService:
    def __init__(self):
        self.aqi_categories = {
            (0, 50): ("Good", "✅"),
            (51, 100): ("Moderate", "🟡"),
            (101, 200): ("Poor", "🟠"),
            (201, 300): ("Very Poor", "🔴"),
            (301, 500): ("Severe", "🔴🔴")
        }
    
    async def get_current_aqi(self, ward_id: str) -> Dict[str, Any]:
        """Get current AQI for ward"""
        
        try:
            # MVP: Mock data (replace with real API later)
            aqi = random.randint(40, 280)
            
            # Determine category
            category = "Unknown"
            emoji = "❓"
            for (min_val, max_val), (cat, em) in self.aqi_categories.items():
                if min_val <= aqi <= max_val:
                    category = cat
                    emoji = em
                    break
            
            data = {
                "ward_id": ward_id,
                "aqi": aqi,
                "category": category,
                "emoji": emoji,
                "pm2_5": random.randint(5, 150),
                "pm10": random.randint(10, 200),
                "no2": random.randint(5, 100),
                "so2": random.randint(5, 80),
                "timestamp": datetime.utcnow()
            }
            
            # Store in DB
            collection = get_pollution_data_collection()
            await collection.insert_one(data)
            
            return {
                "success": True,
                "data": data
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def predict_pollution_spike(self, ward_id: str, hours: int = 24) -> Dict[str, Any]:
        """Predict AQI 24 hours ahead"""
        
        try:
            current = await self.get_current_aqi(ward_id)
            if not current["success"]:
                return current
            
            current_aqi = current["data"]["aqi"]
            predicted_aqi = current_aqi + random.randint(5, 35)
            
            spike_probability = min((predicted_aqi - current_aqi) / 200, 1.0)
            
            if predicted_aqi > 200:
                recommendation = "🚨 SEVERE: Stay indoors, wear N95 masks"
            elif predicted_aqi > 150:
                recommendation = "⚠️ HIGH: Wear N95 masks & reduce outdoor activities"
            elif predicted_aqi > 100:
                recommendation = "🟡 MODERATE: Limit outdoor activities"
            else:
                recommendation = "✅ GOOD: Air quality acceptable"
            
            return {
                "success": True,
                "ward_id": ward_id,
                "current_aqi": current_aqi,
                "predicted_aqi": predicted_aqi,
                "hours_ahead": hours,
                "spike_probability": round(spike_probability, 2),
                "recommendation": recommendation
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_ward_pollution_stats(self, ward_id: str) -> Dict[str, Any]:
        """Get 7-day pollution stats for ward"""
        
        try:
            collection = get_pollution_data_collection()
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            data_points = await collection.find({
                "ward_id": ward_id,
                "timestamp": {"$gte": week_ago}
            }).sort("timestamp", -1).to_list(length=None)
            
            if not data_points:
                return {
                    "success": False,
                    "error": "No data available"
                }
            
            aqi_values = [d["aqi"] for d in data_points]
            avg_aqi = sum(aqi_values) / len(aqi_values)
            max_aqi = max(aqi_values)
            min_aqi = min(aqi_values)
            
            return {
                "success": True,
                "ward_id": ward_id,
                "data_points": len(data_points),
                "average_aqi": round(avg_aqi, 1),
                "max_aqi": max_aqi,
                "min_aqi": min_aqi,
                "trend": "worsening" if aqi_values > avg_aqi else "improving"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


pollution_service = PollutionService()

def get_pollution_service():
    return pollution_service
