"""
Tests for health check module.
"""
import pytest

from rfsn_hybrid.health import (
    HealthChecker,
    HealthStatus,
    SystemHealth,
    run_health_checks,
    check_model_health,
)


class TestHealthStatus:
    """Test individual health status."""
    
    def test_healthy_status(self):
        status = HealthStatus(
            name="test",
            healthy=True,
            message="All good",
        )
        assert status.healthy
        assert status.name == "test"
    
    def test_unhealthy_status(self):
        status = HealthStatus(
            name="test",
            healthy=False,
            message="Something wrong",
        )
        assert not status.healthy


class TestHealthChecker:
    """Test health checker functionality."""
    
    def test_default_checks_exist(self):
        checker = HealthChecker()
        # Should have default checks
        assert "python_version" in checker._checks
        assert "dependencies" in checker._checks
    
    def test_run_single_check(self):
        checker = HealthChecker()
        status = checker.run_check("python_version")
        
        # Python version we're running should pass
        assert status.healthy
        assert "Python" in status.message
    
    def test_run_all_checks(self):
        checker = HealthChecker()
        health = checker.run_all()
        
        assert isinstance(health, SystemHealth)
        assert len(health.checks) >= 2
        assert health.timestamp is not None
    
    def test_custom_check(self):
        checker = HealthChecker()
        
        def my_check():
            return HealthStatus(
                name="custom",
                healthy=True,
                message="Custom check passed",
            )
        
        checker.add_check("custom", my_check)
        status = checker.run_check("custom")
        
        assert status.healthy
        assert "Custom check" in status.message
    
    def test_failing_check_captured(self):
        checker = HealthChecker()
        
        def bad_check():
            raise RuntimeError("Boom!")
        
        checker.add_check("bad", bad_check)
        status = checker.run_check("bad")
        
        assert not status.healthy
        assert "Boom" in status.message
    
    def test_unknown_check(self):
        checker = HealthChecker()
        status = checker.run_check("nonexistent")
        
        assert not status.healthy
        assert "Unknown" in status.message


class TestSystemHealth:
    """Test system health aggregation."""
    
    def test_to_dict(self):
        health = SystemHealth(
            healthy=True,
            checks=[
                HealthStatus(name="test1", healthy=True, message="OK"),
                HealthStatus(name="test2", healthy=True, message="OK"),
            ],
            timestamp="2024-01-01T00:00:00",
        )
        
        d = health.to_dict()
        
        assert d["healthy"] == True
        assert len(d["checks"]) == 2
        assert d["timestamp"] == "2024-01-01T00:00:00"
    
    def test_unhealthy_if_any_check_fails(self):
        health = SystemHealth(
            healthy=False,
            checks=[
                HealthStatus(name="good", healthy=True, message="OK"),
                HealthStatus(name="bad", healthy=False, message="Failed"),
            ],
            timestamp="2024-01-01T00:00:00",
        )
        
        assert not health.healthy


class TestModelHealth:
    """Test model health check."""
    
    def test_empty_path(self):
        status = check_model_health("")
        assert not status.healthy
        assert "configured" in status.message.lower()
    
    def test_nonexistent_path(self):
        status = check_model_health("/nonexistent/model.gguf")
        assert not status.healthy
        assert "not found" in status.message.lower()


class TestGlobalHealthChecker:
    """Test global health check function."""
    
    def test_run_health_checks(self):
        health = run_health_checks()
        
        assert isinstance(health, SystemHealth)
        assert health.timestamp is not None
