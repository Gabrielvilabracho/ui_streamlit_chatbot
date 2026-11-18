-- Optional SQL-view validation access, NOT an Agent/Search deployment.
-- Run only after the prerequisites and privilege audit in the policy guide.
-- These grants are additive; they do not remove existing/inherited access.
-- No source-table, classification-table, ownership, future-object or PUBLIC grants.

GRANT SELECT ON VIEW DATALAB.SPAIN.SOFIA_GENERAL_CHUNKS
  TO ROLE GG_APP_SOYOU_DATALAB_USER;

GRANT SELECT ON VIEW DATALAB.SPAIN.SOFIA_PRIVACY_CHUNKS
  TO ROLE GG_APP_SOYOU_DATALAB_DPO;

GRANT SELECT ON VIEW DATALAB.SPAIN.SOFIA_CREDIT_AFTERSALES_CHUNKS
  TO ROLE GG_APP_SP_DATALAB_CREDIT_AFTERSALES;
