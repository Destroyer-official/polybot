use pyo3::prelude::*;
use serde_json::Value;

/// Scans orderbook JSON for arbitrage opportunities.
/// Returns: (Found_Bool, Buy_Price_YES, Buy_Price_NO)
#[pyfunction]
fn find_arb(orderbook_json: String, min_profit: f64) -> PyResult<(bool, f64, f64)> {
    // 1. Parse JSON (Fast)
    let v: Value = serde_json::from_str(&orderbook_json).unwrap_or(Value::Null);

    // 2. Extract Best Ask Prices (Sellers)
    // "rewards" structure usually holds the YES (0) and NO (1) tokens
    let yes_price = v["rewards"][0]["price"].as_f64().unwrap_or(1.0);
    let no_price = v["rewards"][1]["price"].as_f64().unwrap_or(1.0);

    // 3. Dynamic Fee Logic (Polymarket fee increases near 50 cents)
    // Formula: Max(0.1%, 3% * VolatilityFactor)
    let fee_yes = (0.001f64).max(0.03 * (1.0 - (2.0 * yes_price - 1.0).abs()));
    let fee_no = (0.001f64).max(0.03 * (1.0 - (2.0 * no_price - 1.0).abs()));

    // 4. Calculate Total Cost for $1.00 Payout
    let total_cost = yes_price + fee_yes + no_price + fee_no;

    // 5. Check Profit (Cost must be less than $1.00 minus desired profit)
    if total_cost < (1.0 - min_profit) {
        return Ok((true, yes_price, no_price));
    }

    Ok((false, 0.0, 0.0))
}

#[pymodule]
fn rust_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(find_arb, m)?)?;
    Ok(())
}
