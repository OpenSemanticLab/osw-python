.DEFAULT_GOAL := help

.PHONY: install
install: ## Install the virtual environment and pre-commit hooks
	@echo ">> Creating virtual environment using uv"
	@uv sync
	@uv run pre-commit install

.PHONY: check
check: ## Run code quality tools
	@echo ">> Checking lock file consistency with 'pyproject.toml'"
	@uv lock --locked
	@echo ">> Linting code: Running pre-commit"
	@uv run pre-commit run -a
	@echo ">> Static type checking: Running ty"
	@uv run ty check
	@echo ">> Checking for obsolete dependencies: Running deptry"
	@uv run deptry src

.PHONY: test
test: ## Test the code with pytest (integration tests excluded, see pyproject.toml)
	@echo ">> Testing code: Running pytest"
	@uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml

.PHONY: test-integration
test-integration: ## Run integration tests (set WIKI_DOMAIN, WIKI_USERNAME, WIKI_PASSWORD [, DB_USERNAME, DB_PASSWORD]; tests skip where credentials are missing)
	@echo ">> Testing code: Running pytest on tests/integration"
	@uv run python -m pytest tests/integration -o addopts="" \
		$(if $(WIKI_DOMAIN),--wiki_domain "$(WIKI_DOMAIN)") \
		$(if $(WIKI_USERNAME),--wiki_username "$(WIKI_USERNAME)") \
		$(if $(WIKI_PASSWORD),--wiki_password "$(WIKI_PASSWORD)") \
		$(if $(DB_USERNAME),--db_username "$(DB_USERNAME)") \
		$(if $(DB_PASSWORD),--db_password "$(DB_PASSWORD)")

.PHONY: build
build: clean-build ## Build wheel and sdist
	@echo ">> Creating wheel and sdist files"
	@uv build

.PHONY: clean-build
clean-build: ## Remove build artifacts
	@echo ">> Removing build artifacts"
	@uv run python -c "import shutil; shutil.rmtree('dist', ignore_errors=True)"

.PHONY: publish
publish: ## Publish a release to PyPI (CI-only via OIDC trusted publishing)
	@echo "Publishing happens in CI via OIDC trusted publishing (on-release-main.yml)."
	@echo "Push a version tag (v*) to trigger a release."

.PHONY: docs
docs: ## Build and serve the documentation locally
	@uv run zensical serve

.PHONY: docs-test
docs-test: ## Test if documentation can be built without warnings or errors
	@uv run zensical build -s

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
