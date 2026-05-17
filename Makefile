.PHONY: test audit deploy clean

test:
	powershell.exe -ExecutionPolicy Bypass -File .\tests\live_demo_trigger.ps1

audit:
	powershell.exe -ExecutionPolicy Bypass -File .\scripts\security_audit.sh

deploy:
	bash scripts/remote_deploy.sh

clean:
	rm -rf __pycache__ src/__pycache__ *.log
