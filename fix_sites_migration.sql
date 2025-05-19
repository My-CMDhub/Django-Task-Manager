-- Mark sites migrations as applied
INSERT INTO django_migrations (app, name, applied) 
VALUES 
('sites', '0001_initial', datetime('now')),
('sites', '0002_alter_domain_unique', datetime('now')); 