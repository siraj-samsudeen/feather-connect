-- The audit log refuses TRUNCATE too, the owner included (design point 16):
-- the rights keep the app user from it, but an app that signs in as the owner
-- would otherwise empty the log. An old month still leaves by DETACH or DROP.

CREATE TRIGGER audit_refuse_truncate BEFORE TRUNCATE ON fcon.audit
    FOR EACH STATEMENT EXECUTE FUNCTION fcon.audit_refuse_change();
