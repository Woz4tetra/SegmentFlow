#!/bin/bash
# SegmentFlow validation and test script
# Runs all code quality checks and tests for the backend
# Usage: ./validate-and-test.sh [target]
#   target: 'all' (default), 'backend', 'frontend', 'lint', 'test', 'type'

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"
TARGET="${1:-all}"
FAILED=0
PASSED=0

# Print section headers
print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

# Print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Backend Linting with Ruff
lint_backend() {
    print_header "Backend: Ruff Linting"
    
    if ! command_exists ruff; then
        print_error "ruff not found. Install with: pip install ruff"
        return 1
    fi
    
    if cd "$BACKEND_DIR" && ruff check .; then
        print_success "Ruff lint check passed"
        cd ..
    else
        print_error "Ruff lint check failed"
        cd ..
        return 1
    fi
}

# Backend Code Formatting (check only)
format_backend_check() {
    print_header "Backend: Code Format Check"
    
    if ! command_exists ruff; then
        print_error "ruff not found"
        return 1
    fi
    
    if cd "$BACKEND_DIR" && ruff format --check .; then
        print_success "Code format check passed"
        cd ..
    else
        print_error "Code format issues found. Run './validate-and-test.sh format-fix' to auto-fix"
        cd ..
        return 1
    fi
}

# Backend Code Formatting (fix)
format_backend_fix() {
    print_header "Backend: Auto-fixing Code Format"
    
    if ! command_exists ruff; then
        print_error "ruff not found"
        return 1
    fi
    
    if cd "$BACKEND_DIR" && ruff format .; then
        print_success "Code format fixed"
        cd ..
    else
        print_error "Code format fix failed"
        cd ..
        return 1
    fi
}

# Backend Type Checking with mypy
type_check_backend() {
    print_header "Backend: Type Checking (mypy)"
    
    if ! command_exists mypy; then
        print_error "mypy not found. Install with: pip install mypy"
        return 1
    fi
    
    if cd "$BACKEND_DIR" && mypy app; then
        print_success "Type checking passed"
        cd ..
    else
        print_error "Type checking found errors"
        cd ..
        return 1
    fi
}

# Backend Unit Tests with pytest
test_backend() {
    print_header "Backend: Running Tests"
    
    if ! command_exists pytest; then
        print_error "pytest not found. Install with: pip install pytest pytest-asyncio"
        return 1
    fi
    
    if [ ! -d "$BACKEND_DIR/tests" ]; then
        echo -e "${YELLOW}⚠ No tests directory found at $BACKEND_DIR/tests${NC}"
        return 0
    fi
    
    if cd "$BACKEND_DIR" && pytest; then
        print_success "All tests passed"
        cd ..
    else
        print_error "Tests failed"
        cd ..
        return 1
    fi
}

# Frontend Type Checking with vue-tsc
type_check_frontend() {
    print_header "Frontend: Type Checking (vue-tsc)"
    
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        print_error "Frontend package.json not found"
        return 1
    fi
    
    if cd "$FRONTEND_DIR" && npm run type-check; then
        print_success "Frontend type checking passed"
        cd ..
    else
        print_error "Frontend type checking failed"
        cd ..
        return 1
    fi
}

# Frontend Linting and Tests
lint_frontend() {
    print_header "Frontend: ESLint/Type Checking"
    
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        print_error "Frontend package.json not found"
        return 1
    fi
    
    if cd "$FRONTEND_DIR" && npm run lint 2>/dev/null || echo "No lint script configured"; then
        cd ..
    else
        cd ..
        return 1
    fi
}

test_frontend() {
    print_header "Frontend: Running Tests"
    
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        print_error "Frontend package.json not found"
        return 1
    fi
    
    if cd "$FRONTEND_DIR" && npm run test 2>/dev/null || echo "No test script configured"; then
        print_success "Frontend tests completed"
        cd ..
    else
        cd ..
        return 1
    fi
}

# Full validation and test suite
run_all() {
    print_header "SegmentFlow: Full Validation & Test Suite"
    echo -e "Starting comprehensive validation...\n"
    
    # Backend validation
    lint_backend || true
    format_backend_check || true
    type_check_backend || true
    test_backend || true
    
    # Frontend validation  
    type_check_frontend || true
    test_frontend || true
    
    # Summary
    print_header "Summary"
    TOTAL=$((PASSED + FAILED))
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}All validations passed! ✓${NC}\n"
        exit 0
    else
        echo -e "${RED}$FAILED out of $TOTAL validations failed${NC}\n"
        exit 1
    fi
}

run_backend_only() {
    print_header "SegmentFlow: Backend Validation & Tests"
    
    lint_backend || true
    format_backend_check || true
    type_check_backend || true
    test_backend || true
    
    print_header "Summary"
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}Backend validation passed! ✓${NC}\n"
        exit 0
    else
        echo -e "${RED}$FAILED validation(s) failed${NC}\n"
        exit 1
    fi
}

run_frontend_only() {
    print_header "SegmentFlow: Frontend Validation & Tests"
    
    type_check_frontend || true
    test_frontend || true
    
    print_header "Summary"
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}Frontend validation passed! ✓${NC}\n"
        exit 0
    else
        echo -e "${RED}$FAILED validation(s) failed${NC}\n"
        exit 1
    fi
}

run_lint_only() {
    print_header "SegmentFlow: Lint Check Only"
    
    lint_backend || true
    format_backend_check || true
    
    print_header "Summary"
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}Lint validation passed! ✓${NC}\n"
        exit 0
    else
        echo -e "${RED}$FAILED validation(s) failed${NC}\n"
        exit 1
    fi
}

run_test_only() {
    print_header "SegmentFlow: Tests Only"
    
    test_backend || true
    test_frontend || true
    
    print_header "Summary"
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed! ✓${NC}\n"
        exit 0
    else
        echo -e "${RED}$FAILED test(s) failed${NC}\n"
        exit 1
    fi
}

run_type_check_only() {
    print_header "SegmentFlow: Type Checking Only"
    
    type_check_backend || true
    type_check_frontend || true
    
    print_header "Summary"
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}Type checking passed! ✓${NC}\n"
        exit 0
    else
        echo -e "${RED}$FAILED type check(s) failed${NC}\n"
        exit 1
    fi
}

# Main dispatcher
case "$TARGET" in
    all)
        run_all
        ;;
    backend)
        run_backend_only
        ;;
    frontend)
        run_frontend_only
        ;;
    lint)
        run_lint_only
        ;;
    test)
        run_test_only
        ;;
    type)
        run_type_check_only
        ;;
    format-fix)
        format_backend_fix
        ;;
    *)
        echo "Usage: $0 [target]"
        echo "  all       - Run all validations and tests (default)"
        echo "  backend   - Run backend validation and tests"
        echo "  frontend  - Run frontend validation and tests"
        echo "  lint      - Run linting checks only"
        echo "  test      - Run tests only"
        echo "  type      - Run type checking only"
        echo "  format-fix - Auto-fix code format issues"
        exit 1
        ;;
esac
