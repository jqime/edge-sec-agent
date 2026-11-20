.PHONY: test audit deploy clean pre-commit

test:
	powershell.exe -ExecutionPolicy Bypass -File .\tests\live_demo_trigger.ps1

audit:
	bash scripts/security_audit.sh

deploy:
	bash scripts/remote_deploy.sh

clean:
	rm -rf __pycache__ src/__pycache__ *.log

pre-commit:
	pre-commit install
	pre-commit run --all-files
