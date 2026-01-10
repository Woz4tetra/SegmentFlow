#!/bin/bash

# Script to initialize the frontend development environment and install dependencies
# This script verifies Node.js and npm, installs packages, and runs basic checks

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REQUIRED_NODE_MAJOR=18
REQUIRED_NODE_MINOR=0

# Resolve script directory (frontend root)
FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_header() {
  echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_warn() {
  echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

check_node() {
  print_header "Checking Node.js and npm"

  if ! command -v node >/dev/null 2>&1; then
    print_error "Node.js not found. Please install Node.js >= ${REQUIRED_NODE_MAJOR}.x"
    echo "Linux (nvm) quick setup:"
    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
    echo "  source ~/.nvm/nvm.sh && nvm install ${REQUIRED_NODE_MAJOR} && nvm use ${REQUIRED_NODE_MAJOR}"
    exit 1
  fi

  if ! command -v npm >/dev/null 2>&1; then
    print_error "npm not found. Please ensure npm is installed with Node.js"
    exit 1
  fi

  local node_ver
  node_ver=$(node -v | sed 's/^v//')
  local node_major; node_major=$(echo "$node_ver" | cut -d. -f1)
  local node_minor; node_minor=$(echo "$node_ver" | cut -d. -f2)

  echo "Using Node.js v${node_ver}"

  if [ "$node_major" -lt "$REQUIRED_NODE_MAJOR" ] || { [ "$node_major" -eq "$REQUIRED_NODE_MAJOR" ] && [ "$node_minor" -lt "$REQUIRED_NODE_MINOR" ]; }; then
    print_error "Node.js v${REQUIRED_NODE_MAJOR}.${REQUIRED_NODE_MINOR}+ required. Current: v${node_ver}"
    echo "If using nvm:"
    echo "  nvm install ${REQUIRED_NODE_MAJOR} && nvm use ${REQUIRED_NODE_MAJOR}"
    exit 1
  fi

  print_success "Node.js and npm are available"
}

install_deps() {
  print_header "Installing frontend dependencies"
  cd "$FRONTEND_DIR"

  if [ -f package-lock.json ]; then
    echo "Detected package-lock.json; using 'npm ci'"
    npm ci
  else
    print_warn "No package-lock.json found; using 'npm install'"
    npm install
  fi

  print_success "Dependencies installed"
}

run_type_check() {
  print_header "Running TypeScript/Vue type-check"
  if npm run type-check; then
    print_success "Type-check passed"
  else
    print_error "Type-check failed"
    exit 1
  fi
}

run_build_check() {
  print_header "Running production build"
  if npm run build; then
    print_success "Build succeeded"
  else
    print_error "Build failed"
    exit 1
  fi
}

summary() {
  print_header "Frontend environment setup complete"
  echo "Location: $FRONTEND_DIR"
  echo "Next steps:"
  echo "  - Start dev server: npm run dev"
  echo "  - Preview build:   npm run preview"
}

main() {
  echo "Frontend root: $FRONTEND_DIR"
  check_node
  install_deps
  run_type_check
  run_build_check
  summary
}

main
