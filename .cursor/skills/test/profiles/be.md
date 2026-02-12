# Backend Test Profile

This profile defines test generation patterns for backend (API/unit) testing.

## Test Framework Detection

| File | Framework | Language |
|------|-----------|----------|
| `pytest.ini`, `pyproject.toml` (pytest section) | pytest | Python |
| `setup.cfg` (tool:pytest) | pytest | Python |
| `package.json` (jest) | jest | Node.js |
| `package.json` (vitest) | vitest | Node.js |
| `package.json` (mocha) | mocha | Node.js |
| `go.mod` | go test | Go |
| `pom.xml` | JUnit | Java |
| `build.gradle` | JUnit | Java/Kotlin |

## Test File Naming Convention

| Framework | Source File | Test File |
|-----------|-------------|-----------|
| pytest | `src/services/alert.py` | `tests/services/test_alert.py` |
| jest/vitest | `src/services/alert.ts` | `src/services/alert.test.ts` or `__tests__/alert.test.ts` |
| go test | `pkg/alert/service.go` | `pkg/alert/service_test.go` |
| JUnit | `src/main/.../AlertService.java` | `src/test/.../AlertServiceTest.java` |

## Test Structure Template

### Python (pytest)

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from {module_path} import {ClassName}


class Test{ClassName}:
    """Tests for {ClassName} - {FR_IDs}"""

    @pytest.fixture
    def instance(self):
        """Create test instance with mocked dependencies"""
        return {ClassName}()

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return MagicMock()

    # Happy path tests
    def test_{method}_success(self, instance):
        """
        Given: Valid input
        When: {method} is called
        Then: Expected result returned
        """
        result = instance.{method}(valid_input)
        assert result is not None

    # Error case tests
    def test_{method}_invalid_input(self, instance):
        """
        Given: Invalid input
        When: {method} is called
        Then: Appropriate error raised
        """
        with pytest.raises(ValueError):
            instance.{method}(invalid_input)

    # Edge case tests
    def test_{method}_empty_input(self, instance):
        """
        Given: Empty input
        When: {method} is called
        Then: Handled gracefully
        """
        result = instance.{method}(None)
        assert result == expected_default
```

### TypeScript (jest/vitest)

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { {ClassName} } from '{module_path}';

describe('{ClassName}', () => {
  let instance: {ClassName};

  beforeEach(() => {
    instance = new {ClassName}();
  });

  describe('{method}', () => {
    it('should succeed with valid input', async () => {
      const result = await instance.{method}(validInput);
      expect(result).toBeDefined();
    });

    it('should throw error with invalid input', async () => {
      await expect(instance.{method}(invalidInput))
        .rejects.toThrow('Expected error');
    });

    it('should handle edge case', async () => {
      const result = await instance.{method}(edgeCase);
      expect(result).toEqual(expectedDefault);
    });
  });
});
```

### Go

```go
package {package}_test

import (
    "testing"
    "{module_path}"
)

func Test{MethodName}_Success(t *testing.T) {
    // Given
    svc := {package}.New{ClassName}()
    
    // When
    result, err := svc.{MethodName}(validInput)
    
    // Then
    if err != nil {
        t.Errorf("expected no error, got %v", err)
    }
    if result == nil {
        t.Error("expected result, got nil")
    }
}

func Test{MethodName}_InvalidInput(t *testing.T) {
    svc := {package}.New{ClassName}()
    
    _, err := svc.{MethodName}(invalidInput)
    
    if err == nil {
        t.Error("expected error, got nil")
    }
}
```

## API Test Template

### Python (pytest + httpx/TestClient)

```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from main import app


class TestAlertAPI:
    """API tests for Alert endpoints - {FR_IDs}"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_alerts_success(self, client):
        """GET /api/alerts returns list"""
        response = client.get("/api/alerts")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_alerts_unauthorized(self, client):
        """GET /api/alerts without auth returns 401"""
        response = client.get("/api/alerts", headers={})
        assert response.status_code == 401

    def test_create_alert_success(self, client, auth_headers):
        """POST /api/alerts creates new alert"""
        payload = {"message": "Test alert", "type": "info"}
        response = client.post("/api/alerts", json=payload, headers=auth_headers)
        assert response.status_code == 201
        assert response.json()["id"] is not None

    def test_create_alert_validation_error(self, client, auth_headers):
        """POST /api/alerts with invalid payload returns 422"""
        payload = {"message": ""}  # Invalid: empty message
        response = client.post("/api/alerts", json=payload, headers=auth_headers)
        assert response.status_code == 422
```

### TypeScript (supertest)

```typescript
import request from 'supertest';
import { app } from '../src/app';

describe('Alert API', () => {
  describe('GET /api/alerts', () => {
    it('should return alerts list', async () => {
      const response = await request(app)
        .get('/api/alerts')
        .set('Authorization', `Bearer ${token}`);
      
      expect(response.status).toBe(200);
      expect(Array.isArray(response.body)).toBe(true);
    });

    it('should return 401 without auth', async () => {
      const response = await request(app).get('/api/alerts');
      expect(response.status).toBe(401);
    });
  });

  describe('POST /api/alerts', () => {
    it('should create alert', async () => {
      const response = await request(app)
        .post('/api/alerts')
        .set('Authorization', `Bearer ${token}`)
        .send({ message: 'Test', type: 'info' });
      
      expect(response.status).toBe(201);
      expect(response.body.id).toBeDefined();
    });
  });
});
```

## Test Run Commands

| Framework | Run All | Run Specific | With Coverage |
|-----------|---------|--------------|---------------|
| pytest | `pytest` | `pytest tests/path/test_file.py` | `pytest --cov=src` |
| jest | `npm test` | `npm test -- path/file.test.ts` | `npm test -- --coverage` |
| vitest | `npx vitest` | `npx vitest path/file.test.ts` | `npx vitest --coverage` |
| go test | `go test ./...` | `go test ./pkg/alert/...` | `go test -cover ./...` |

## Mocking Patterns

### Database Mocking

```python
# Python - pytest with mock
@pytest.fixture
def mock_session(mocker):
    session = mocker.MagicMock()
    session.query.return_value.filter.return_value.first.return_value = mock_data
    return session
```

```typescript
// TypeScript - vitest with vi
vi.mock('../src/db', () => ({
  prisma: {
    alert: {
      findMany: vi.fn().mockResolvedValue([mockAlert]),
      create: vi.fn().mockResolvedValue(mockAlert),
    },
  },
}));
```

### External Service Mocking

```python
# Python - responses library for HTTP mocking
import responses

@responses.activate
def test_external_api_call():
    responses.add(
        responses.GET,
        "https://api.external.com/data",
        json={"result": "mocked"},
        status=200
    )
    result = service.call_external()
    assert result == "mocked"
```

## Assertion Patterns

| Assertion Type | Python (pytest) | TypeScript (vitest) |
|---------------|-----------------|---------------------|
| Equal | `assert a == b` | `expect(a).toBe(b)` |
| Deep equal | `assert a == b` | `expect(a).toEqual(b)` |
| Truthy | `assert value` | `expect(value).toBeTruthy()` |
| Contains | `assert item in list` | `expect(list).toContain(item)` |
| Raises | `pytest.raises(Error)` | `expect().rejects.toThrow()` |
| Called | `mock.assert_called()` | `expect(mock).toHaveBeenCalled()` |
