import joblib
import pandas as pd
from pathlib import Path
from typing import Dict, List


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
        "kaggle_anomaly_rate",
        "fault_injection_count",
        "avg_affected_services",
        "fault_impact_score",
    ]

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.model = joblib.load(model_path)

    def _generate_reason(self, features: Dict[str, float], risk_level: int) -> str:
        """
        Generate a human-readable explanation for the predicted risk.
        """

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

    def predict_service_risk(
        self,
        service_features: Dict[str, Dict[str, float]]
    ) -> List[Dict]:
        """
        Predict architectural risk level for each service
        and return ranked, explainable results.
        """

        # --------------------------------------------------
        # Graceful handling of empty input
        # --------------------------------------------------
        if not service_features:
            return []

        rows = []
        services = []

        for service, features in service_features.items():
            row = {}

            # 🔒 Ensure ALL model features exist (schema enforcement)
            for feature in self.MODEL_FEATURES:
                row[feature] = features.get(feature, 0.0)

            row["service"] = service
            rows.append(row)
            services.append(service)

        # --------------------------------------------------
        # Build DataFrame with enforced schema
        # --------------------------------------------------
        df = pd.DataFrame(rows)

        # Force expected columns to exist even if empty
        df = df.reindex(
            columns=self.MODEL_FEATURES + ["service"],
            fill_value=0.0
        )

        if df.empty:
            return []

        X = df[self.MODEL_FEATURES]

        # --------------------------------------------------
        # ML inference
        # --------------------------------------------------
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)

        results = []

        for idx, service in enumerate(services):
            results.append({
                "service": service,
                "predicted_risk_level": int(predictions[idx]),
                "risk_confidence": float(max(probabilities[idx])),
                "reason": self._generate_reason(
                    features=df.iloc[idx].to_dict(),
                    risk_level=int(predictions[idx])
                )
            })

        # Rank by severity and confidence
        results.sort(
            key=lambda x: (x["predicted_risk_level"], x["risk_confidence"]),
            reverse=True
        )

        return results
