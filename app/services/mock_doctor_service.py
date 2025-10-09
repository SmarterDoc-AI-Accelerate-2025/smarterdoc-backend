from typing import List, Optional
from app.models.schemas import FrontendDoctor, FrontendSearchRequest


class MockDoctorService:
    def __init__(self):
        self.mock_doctors = self._create_mock_doctors()
    
    def _create_mock_doctors(self) -> List[FrontendDoctor]:
        """Create a list of mock doctors for testing"""
        return [
            FrontendDoctor(
                id=1,
                name="Dr. Mark Johnson",
                specialty="Family Medicine",
                rating=4.2,
                reviews=424,
                address="120 Hobart St · Utica, NY 13501",
                lat=43.1009,
                lng=-75.2327,
                time="16 minutes",
                insurance_accepted=["Aetna", "Blue Cross", "Cigna"]
            ),
            FrontendDoctor(
                id=2,
                name="Dr. Lisa Chen",
                specialty="Dermatology",
                rating=4.6,
                reviews=320,
                address="50 Main St · Utica, NY 13501",
                lat=43.1059,
                lng=-75.2301,
                time="20 minutes",
                insurance_accepted=["Aetna", "United Healthcare"]
            ),
            FrontendDoctor(
                id=3,
                name="Dr. Kevin Rodriguez",
                specialty="Pediatrics",
                rating=4.8,
                reviews=285,
                address="80 Broad St · Utica, NY 13501",
                lat=43.1021,
                lng=-75.2408,
                time="10 minutes",
                insurance_accepted=["Blue Cross", "Medicaid"]
            ),
            FrontendDoctor(
                id=4,
                name="Dr. Sarah Williams",
                specialty="Cardiology",
                rating=4.5,
                reviews=198,
                address="150 Genesee St · Utica, NY 13501",
                lat=43.0987,
                lng=-75.2289,
                time="25 minutes",
                insurance_accepted=["Aetna", "Cigna", "Medicare"]
            ),
            FrontendDoctor(
                id=5,
                name="Dr. Michael Brown",
                specialty="Orthopedics",
                rating=4.3,
                reviews=312,
                address="200 Columbia St · Utica, NY 13501",
                lat=43.1076,
                lng=-75.2354,
                time="15 minutes",
                insurance_accepted=["Blue Cross", "United Healthcare"]
            ),
            FrontendDoctor(
                id=6,
                name="Dr. Amanda Davis",
                specialty="Neurology",
                rating=4.7,
                reviews=267,
                address="90 Park Ave · Utica, NY 13501",
                lat=43.1034,
                lng=-75.2382,
                time="18 minutes",
                insurance_accepted=["Aetna", "Cigna", "Medicare"]
            )
        ]
    
    def search_doctors(self, search_request: FrontendSearchRequest) -> List[FrontendDoctor]:
        """Mock search function that filters doctors based on query"""
        doctors = self.mock_doctors.copy()
        
        # Filter by search query (specialty or name) - improved matching
        if search_request.query:
            query_lower = search_request.query.lower()
            doctors = [
                doc for doc in doctors 
                if (query_lower in doc.specialty.lower() or 
                    query_lower in doc.name.lower() or
                    any(query_lower in specialty_part.lower() for specialty_part in doc.specialty.split()))
            ]
        
        # Filter by location (mock implementation) - improved matching
        if search_request.location:
            location_lower = search_request.location.lower()
            doctors = [
                doc for doc in doctors 
                if location_lower in doc.address.lower() or "utica" in doc.address.lower()
            ]
        
        # Filter by insurance (mock implementation) - improved matching
        if search_request.insurance:
            insurance_lower = search_request.insurance.lower()
            doctors = [
                doc for doc in doctors 
                if doc.insurance_accepted and any(
                    insurance_lower in ins.lower() for ins in doc.insurance_accepted
                )
            ]
        
        return doctors
    
    def voice_search_doctors(self, voice_query: Optional[str] = None) -> List[FrontendDoctor]:
        """Mock voice search that returns different results based on voice query"""
        if voice_query:
            voice_lower = voice_query.lower()
            
            # Simple keyword matching for demo purposes
            if "pediatric" in voice_lower or "child" in voice_lower or "kids" in voice_lower:
                return [doc for doc in self.mock_doctors if "pediatric" in doc.specialty.lower()]
            elif "skin" in voice_lower or "dermatology" in voice_lower:
                return [doc for doc in self.mock_doctors if "dermatology" in doc.specialty.lower()]
            elif "heart" in voice_lower or "cardiology" in voice_lower:
                return [doc for doc in self.mock_doctors if "cardiology" in doc.specialty.lower()]
            elif "bone" in voice_lower or "orthopedic" in voice_lower:
                return [doc for doc in self.mock_doctors if "orthopedic" in doc.specialty.lower()]
            elif "brain" in voice_lower or "neurology" in voice_lower:
                return [doc for doc in self.mock_doctors if "neurology" in doc.specialty.lower()]
            elif "family" in voice_lower or "primary" in voice_lower:
                return [doc for doc in self.mock_doctors if "family" in doc.specialty.lower()]
        
        # Return all doctors if no specific query or no matches
        return self.mock_doctors.copy()


# Create a singleton instance
mock_doctor_service = MockDoctorService()