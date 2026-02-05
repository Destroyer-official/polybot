use pyo3::prelude::*;
use pyo3::types::PyModule;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Mutex;

// Global fee cache for performance optimization
static FEE_CACHE: Mutex<Option<HashMap<u64, f64>>> = Mutex::new(None);

/// Calculate Polymarket 2025 dynamic fee for a given price.
/// Formula: fee = max(0.001, 0.03 * (1.0 - abs(2.0 * price - 1.0)))
/// 
/// Fee peaks at ~3% near 50% odds and approaches 0.1% at price extremes.
/// Uses caching to optimize repeated calculations.
#[pyfunction]
fn calculate_fee(price: f64) -> PyResult<f64> {
    // Validate price is in valid range [0.0, 1.0]
    if price < 0.0 || price > 1.0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Price must be between 0.0 and 1.0, got {}", price)
        ));
    }

    // Convert price to integer key for caching (6 decimal places precision)
    let cache_key = (price * 1_000_000.0).round() as u64;

    // Check cache first
    {
        let mut cache_guard = FEE_CACHE.lock().unwrap();
        if cache_guard.is_none() {
            *cache_guard = Some(HashMap::new());
        }
        
        if let Some(cached_fee) = cache_guard.as_ref().unwrap().get(&cache_key) {
            return Ok(*cached_fee);
        }
    }

    // Calculate fee using 2025 formula
    // abs(2.0 * price - 1.0) measures distance from 50% odds
    // When price = 0.5: abs(2.0 * 0.5 - 1.0) = 0, fee = 3%
    // When price = 0.0 or 1.0: abs(2.0 * price - 1.0) = 1, fee = 0.1%
    let certainty = (2.0 * price - 1.0).abs();
    let fee = (0.001_f64).max(0.03 * (1.0 - certainty));

    // Store in cache
    {
        let mut cache_guard = FEE_CACHE.lock().unwrap();
        cache_guard.as_mut().unwrap().insert(cache_key, fee);
    }

    Ok(fee)
}

/// Calculate total cost for internal arbitrage including fees.
/// Returns: (yes_fee, no_fee, total_cost)
#[pyfunction]
fn calculate_total_cost(yes_price: f64, no_price: f64) -> PyResult<(f64, f64, f64)> {
    let yes_fee = calculate_fee(yes_price)?;
    let no_fee = calculate_fee(no_price)?;
    
    // Total cost = prices + (prices * fees)
    let total_cost = yes_price + no_price + (yes_price * yes_fee) + (no_price * no_fee);
    
    Ok((yes_fee, no_fee, total_cost))
}

/// Clear the fee cache (useful for testing).
#[pyfunction]
fn clear_fee_cache() -> PyResult<()> {
    let mut cache_guard = FEE_CACHE.lock().unwrap();
    if let Some(cache) = cache_guard.as_mut() {
        cache.clear();
    }
    Ok(())
}

/// Get the current size of the fee cache.
#[pyfunction]
fn get_cache_size() -> PyResult<usize> {
    let cache_guard = FEE_CACHE.lock().unwrap();
    Ok(cache_guard.as_ref().map_or(0, |c| c.len()))
}

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

    // 3. Calculate fees using 2025 dynamic fee formula with caching
    let yes_fee = calculate_fee(yes_price)?;
    let no_fee = calculate_fee(no_price)?;

    // 4. Calculate Total Cost for $1.00 Payout
    // Total cost = prices + (prices * fees)
    let total_cost = yes_price + no_price + (yes_price * yes_fee) + (no_price * no_fee);

    // 5. Check Profit (Cost must be less than $1.00 minus desired profit)
    if total_cost < (1.0 - min_profit) {
        return Ok((true, yes_price, no_price));
    }

    Ok((false, 0.0, 0.0))
}

#[pymodule]
fn rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_fee, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_total_cost, m)?)?;
    m.add_function(wrap_pyfunction!(clear_fee_cache, m)?)?;
    m.add_function(wrap_pyfunction!(get_cache_size, m)?)?;
    m.add_function(wrap_pyfunction!(find_arb, m)?)?;
    Ok(())
}
