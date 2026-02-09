#!/usr/bin/env python3
"""
Monkey-patch for py-clob-client to fix clock skew issues.
This adds a 5-second lag to the POLY_TIMESTAMP header to ensure
the server sees the request as "recent past" within its validity window.

Import this module BEFORE using ClobClient to apply the fix.
"""

import time
import logging

logger = logging.getLogger(__name__)

# Flag to prevent double-patching
_PATCHED = False

def apply_clock_skew_fix(lag_seconds: int = 5):
    """
    Patch py-clob-client to add timestamp lag for clock skew fix.
    
    Args:
        lag_seconds: Number of seconds to lag the timestamp (default 5)
    """
    global _PATCHED
    
    if _PATCHED:
        logger.debug("Clock skew fix already applied")
        return
    
    try:
        from py_clob_client.signer import Signer
        from py_clob_client.order_builder.helpers import get_time
        import py_clob_client.order_builder.helpers as helpers_module
        
        # Save original get_time function
        original_get_time = helpers_module.get_time
        
        def patched_get_time():
            """Return timestamp with lag to fix clock skew."""
            original_time = original_get_time()
            lagged_time = original_time - (lag_seconds * 1000)  # Convert seconds to ms
            return lagged_time
        
        # Patch the helpers module
        helpers_module.get_time = patched_get_time
        
        logger.info(f"✅ Clock skew fix applied: {lag_seconds}s timestamp lag")
        _PATCHED = True
        
    except Exception as e:
        logger.warning(f"Failed to apply clock skew fix: {e}")
        # Try alternative patching approach
        try:
            import py_clob_client.headers.headers as headers_module
            
            original_create_l2_headers = headers_module.create_l2_headers
            
            def patched_create_l2_headers(*args, **kwargs):
                """Create L2 headers with lagged timestamp."""
                headers = original_create_l2_headers(*args, **kwargs)
                if 'POLY_TIMESTAMP' in headers:
                    original_ts = int(headers['POLY_TIMESTAMP'])
                    lagged_ts = original_ts - (lag_seconds * 1000)
                    headers['POLY_TIMESTAMP'] = str(lagged_ts)
                return headers
            
            headers_module.create_l2_headers = patched_create_l2_headers
            logger.info(f"✅ Clock skew fix applied (alt method): {lag_seconds}s timestamp lag")
            _PATCHED = True
            
        except Exception as e2:
            logger.error(f"Failed to apply clock skew fix (alt): {e2}")


# Auto-apply when imported
apply_clock_skew_fix(lag_seconds=5)
