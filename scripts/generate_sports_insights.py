import json
import os

def main():
    accuracy_path = r"e:\code.projects\hodge-rank-clustering\site\data\hodge_winner_accuracy.json"
    agent_path = r"e:\code.projects\hodge-rank-clustering\site\data\hodge_real_sportsbook_agent_strict.json"
    out_path = r"e:\code.projects\hodge-rank-clustering\site\data\sports_market_inefficiency.json"

    if not os.path.exists(accuracy_path) or not os.path.exists(agent_path):
        print("Required sportsbook JSON files not found!")
        return

    with open(accuracy_path, "r") as f:
        acc_data = json.load(f)
    with open(agent_path, "r") as f:
        agent_data = json.load(f)

    acc_summary = acc_data["summary"]
    agent_summary = agent_data["agent"]["summary"]

    # 1. Compile Accuracy Comparison (Hodge vs Elo vs Market Favorite)
    sports = ["CFB", "EPL", "MLB", "NBA", "NFL", "NHL"]
    accuracy_comparison = {}
    for sport in sports:
        hodge_acc = acc_summary["hodge_signal"]["by_sport"][sport]["accuracy_pct"]
        elo_acc = acc_summary["elo"]["by_sport"][sport]["accuracy_pct"]
        market_acc = acc_summary["market_favorite"]["by_sport"][sport]["accuracy_pct"]
        accuracy_comparison[sport] = {
            "hodge": hodge_acc,
            "elo": elo_acc,
            "market_favorite": market_acc,
            "hodge_vs_elo_delta": round(hodge_acc - elo_acc, 2)
        }

    # 2. Compile Home vs Away Yield Pockets (Home vs Away Bias)
    home_away_yields = {}
    by_side = agent_summary["by_side"]
    for sport in sports:
        away_key = f"{sport}:away"
        home_key = f"{sport}:home"

        away_yield = by_side[away_key]["yield_pct"] if away_key in by_side else None
        home_yield = by_side[home_key]["yield_pct"] if home_key in by_side else None

        home_away_yields[sport] = {
            "away_yield_pct": away_yield,
            "home_yield_pct": home_yield,
            "bias_differential": round(away_yield - home_yield, 2) if away_yield is not None and home_yield is not None else None
        }

    combined = {
        "accuracy_comparison": accuracy_comparison,
        "home_away_bias": home_away_yields
    }

    with open(out_path, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"Saved sports market inefficiency insights to {out_path}")

    # Print a text summary
    print("\n--- ACCURACY COMPARISON ---")
    print(f"{'Sport':<6} | {'Hodge':<8} | {'Elo':<8} | {'Delta':<8}")
    print("-" * 38)
    for sport, data in accuracy_comparison.items():
        print(f"{sport:<6} | {data['hodge']:<8}% | {data['elo']:<8}% | {data['hodge_vs_elo_delta']:+8.2f}%")

    print("\n--- HOME VS AWAY YIELD (BIAS) ---")
    print(f"{'Sport':<6} | {'Away Yield':<10} | {'Home Yield':<10} | {'Away-Home Delta':<15}")
    print("-" * 52)
    for sport, data in home_away_yields.items():
        print(f"{sport:<6} | {data['away_yield_pct']:+9.2f}% | {data['home_yield_pct']:+9.2f}% | {data['bias_differential']:+14.2f}%")

if __name__ == "__main__":
    main()
