import typing as t
from sklearn.feature_extraction.text import TfidfVectorizer


class SparseVectorizerClient:

    def __init__(self):
        self.vectorizer = TfidfVectorizer()

        # For demo
        self.vectorizer.fit([
            "Family Medicine, Sports Medicine"
            "Nurse Anesthetist, Certified Registered"
            "Obstetrics & Gynecology"
            "Obstetrics & Gynecology, Gynecology"
            "Obstetrics & Gynecology, Reproductive Endocrinology"
            "Orthopaedic Surgery"
            "Orthopaedic Surgery, Adult Reconstructive Orthopaedic Surgery"
            "Orthopaedic Surgery, Foot and Ankle Surgery"
            "Orthopaedic Surgery, Hand Surgery"
            "Orthopaedic Surgery, Orthopaedic Surgery of the Spine"
            "Orthopaedic Surgery, Orthopaedic Trauma"
            "Orthopaedic Surgery, Pediatric Orthopaedic Surgery"
            "Orthopaedic Surgery, Sports Medicine"
            "Registered Nurse, Reproductive Endocrinology/Infertility"
            "Student in an Organized Health Care Education/Training Program"
        ])

    def get_sparse_embedding(self, text: str) -> t.Dict[str, t.Any]:
        """Generates a sparse vector using the fitted TF-IDF model."""
        if not text:
            return {"dimensions": [], "values": []}

        vector = self.vectorizer.transform([text])[0]
        coo_matrix = vector.tocoo()

        return {
            "dimensions": [int(i) for i in coo_matrix.col],
            "values": [float(v) for v in coo_matrix.data]
        }
