from pathlib import Path
from pprint import pprint

import pandas as pd


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "campaigns.csv"


def analyze_campaigns() -> dict:
    df = pd.read_csv(DATA_FILE)

    df["ctr"] = (df["clicks"] / df["impressions"]) * 100
    df["roas"] = df["revenue"] / df["spend"]

    total_spend = df["spend"].sum()
    total_impressions = df["impressions"].sum()
    total_clicks = df["clicks"].sum()
    total_revenue = df["revenue"].sum()

    return {
        "campaigns": df.to_dict(orient="records"),
        "summary": {
            "total_spend": float(total_spend),
            "total_impressions": int(total_impressions),
            "global_ctr": float((total_clicks / total_impressions) * 100),
            "global_roas": float(total_revenue / total_spend),
        },
    }


if __name__ == "__main__":
    pprint(analyze_campaigns())
