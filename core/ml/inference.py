import joblib
import pandas as pd
from pathlib import Path
from typing import Dict, List


def generate_reason(features: Dict[str, float], risk_level: int) -> str:
    reasons = []

    if features.get("betweenness_centrality", 0.0) > 0.3:
        reasons.append(
            "high betweenness centrality indicates the service is a critical communication hub"
        )

    if features.get("fan_in", 0.0) > 3:
        reasons.append(
            "high fan-in suggests tight coupling with multiple dependent services"
        )

    if features.get("dependency_depth", 0.0) > 2:
        reasons.append(
            "deep dependency chains increase fault propagation risk"
        )

    if features.get("error_rate", 0.0) > 0.1:
        reasons.append(
            "elevated error rate suggests runtime instability"
        )

    if features.get("perc95_rt", 0.0) > 300:
        reasons.append(
            "high p95 latency indicates potential performance bottlenecks"
        )

    if features.get("is_gateway", 0.0) == 1.0:
        reasons.append(
            "service acts as an API Gateway and may represent a single point of failure"
        )

    if not reasons:
        reasons.append(
            "low structural complexity and absence of anomaly or fault signals"
        )

    labels = {0: "Low risk", 1: "Medium risk", 2: "High risk"}
    return f"{labels[risk_level]} due to " + ", ".join(reasons)


class DevArchAIInferenceEngine:
    """
    Loads trained DevArchAI models and performs
    explainable architectural risk inference.
    """

    MODEL_FEATURES = [
        "fan_in",
        "fan_out",
        "degree_centrality",
        "in_degree_centrality",
        "out_degree_centrality",
        "betweenness_centrality",
        "closeness_centrality",
        "dependency_depth",
        "reachable_services",
        "is_gateway",
        "is_config_service",
        "anomaly_rate",
        "error_rate",
        "req_rate",
        "req_ok",
        "req_ko",
        "perc95_rt",
        "avg_rt",
        "avg_ok_rt",
        "avg_ko_rt",
        "kaggle_anomaly_rate",
        "fault_injection_count",
        "avg_affected_services",
        "fault_impact_score",
    ]

    MEDIUM_THRESHOLD = 0.4
    HIGH_THRESHOLD = 0.7

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.model = joblib.load(model_path)

    def _generate_reason(self, features: Dict[str, float], risk_level: int) -> str:
        """
        Generate a human-readable explanation for the predicted risk.
        """
        return generate_reason(features, risk_level)

    def predict_service_risk(
        self,
        service_features: Dict[str, Dict[str, float]]
    ) -> List[Dict]:
        """
        Predict architectural risk level for each service
        and return ranked, explainable results.
        """

        if not service_features:
            return []

        rows = []
        services = []

        for service, features in service_features.items():
            row = {}

            for feature in self.MODEL_FEATURES:
                row[feature] = features.get(feature, 0.0)

            row["service"] = service
            rows.append(row)
            services.append(service)

        df = pd.DataFrame(rows)

        df = df.reindex(
            columns=self.MODEL_FEATURES + ["service"],
            fill_value=0.0
        )

        if df.empty:
            return []

        X = df[self.MODEL_FEATURES]

        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)
        class_labels = list(getattr(self.model, "classes_", []))

        results = []

        for idx, service in enumerate(services):
            if len(class_labels) == 2:
                # Binary model -> map probability into Low/Medium/High tiers
                pos_idx = class_labels.index(1) if 1 in class_labels else 1
                risk_score = float(probabilities[idx][pos_idx])
                if risk_score >= self.HIGH_THRESHOLD:
                    risk_level = 2
                elif risk_score >= self.MEDIUM_THRESHOLD:
                    risk_level = 1
                else:
                    risk_level = 0
                # Confidence should reflect the predicted tier (not just the positive class prob)
                # Low risk => confidence = 1 - risk_score, Medium/High => confidence = risk_score
                confidence = (1.0 - risk_score) if risk_level == 0 else risk_score
            else:
                risk_level = int(predictions[idx])
                confidence = float(max(probabilities[idx]))

            results.append({
                "service": service,
                "predicted_risk_level": int(risk_level),
                "risk_confidence": float(confidence),
                "reason": self._generate_reason(
                    features=df.iloc[idx].to_dict(),
                    risk_level=int(risk_level)
                )
            })

        results.sort(
            key=lambda x: (x["predicted_risk_level"], x["risk_confidence"]),
            reverse=True
        )

        return results
