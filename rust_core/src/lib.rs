use pyo3::prelude::*;
use serde_json::Value;

#[pyfunction]
fn find_arb(orderbook_json: String, min_profit: f64) -> PyResult<(bool, f64, f64)> {
    let v: Value = serde_json::from_str(&orderbook_json).unwrap_or(Value::Null);

    // Extract Ask Prices (Sellers)
    let yes_price = v["rewards"][0]["price"].as_f64().unwrap_or(1.0);
    let no_price = v["rewards"][1]["price"].as_f64().unwrap_or(1.0);

    // Dynamic Fee Logic (Polymarket fee increases near 50%)
    let fee_yes = (0.001f64).max(0.03 * (1.0 - (2.0 * yes_price - 1.0).abs()));
    let fee_no = (0.001f64).max(0.03 * (1.0 - (2.0 * no_price - 1.0).abs()));

    // Total Cost to buy $1.00 payout
    let total_cost = yes_price + fee_yes + no_price + fee_no;

    // If Cost < $0.99 (Guaranteed Profit), Signal BUY
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
