ROOT_DIR := ..

.PHONY: bootstrap infra-bootstrap app-bootstrap test synth diff deploy smoke

bootstrap infra-bootstrap:
	$(MAKE) -C $(ROOT_DIR) infra-bootstrap

app-bootstrap:
	$(MAKE) -C $(ROOT_DIR) bootstrap

test:
	$(MAKE) -C $(ROOT_DIR) infra-test

synth:
	$(MAKE) -C $(ROOT_DIR) cdk-synth

diff:
	$(MAKE) -C $(ROOT_DIR) cdk-diff

deploy:
	$(MAKE) -C $(ROOT_DIR) cdk-deploy

smoke:
	$(MAKE) -C $(ROOT_DIR) smoke
