CREATE SCHEMA "public";
CREATE SCHEMA "cle_v2";
CREATE SCHEMA "legacy";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE TABLE "cle_v2"."_lang_map" (
	"hudoc" text PRIMARY KEY,
	"iso" text NOT NULL
);
CREATE TABLE "cle_v2"."case_citation" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_citation_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"source_case_id" bigint,
	"target_case_id" bigint,
	"target_ecli_raw" text,
	"target_celex_raw" text,
	"relation_type" text,
	"source_dataset" text NOT NULL,
	"weight" integer DEFAULT 1,
	"context_segment_id" bigint,
	"is_cross_jurisdiction" boolean DEFAULT false,
	"extractor_at" timestamp with time zone DEFAULT now(),
	"extractor_version" text
);
CREATE TABLE "cle_v2"."case_citation_counts" (
	"case_id" bigint PRIMARY KEY,
	"cites_count" integer DEFAULT 0 NOT NULL,
	"cited_by_count" integer DEFAULT 0 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."case_cluster" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_cluster_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"snapshot_id" bigint,
	"algorithm" text,
	"label" text,
	"size" integer
);
CREATE TABLE "cle_v2"."case_cluster_membership" (
	"cluster_id" bigint,
	"case_id" bigint,
	CONSTRAINT "case_cluster_membership_pkey" PRIMARY KEY("cluster_id","case_id")
);
CREATE TABLE "cle_v2"."case_domain" (
	"case_id" bigint,
	"domain_id" bigint,
	CONSTRAINT "case_domain_pkey" PRIMARY KEY("case_id","domain_id")
);
CREATE TABLE "cle_v2"."case_entity" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_entity_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint,
	"entity_type" text,
	"canonical_name" text,
	"surface_form" text,
	"uri" text,
	"char_start" integer,
	"char_end" integer,
	"confidence" real
);
CREATE TABLE "cle_v2"."case_judge" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_judge_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint,
	"judge_id" bigint,
	"role" text,
	CONSTRAINT "case_judge_case_id_judge_id_role_key" UNIQUE("case_id","judge_id","role")
);
CREATE TABLE "cle_v2"."case_law_reference" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_law_reference_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL,
	"legislation_id" bigint,
	"provision_id" bigint,
	"raw_scheme" text,
	"raw_resource" text,
	"raw_subdivision" text,
	"raw_label_id" bigint,
	"raw_reference" text,
	"version_date" date,
	"role" text DEFAULT 'cited' NOT NULL,
	"source_dataset" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."case_network_metric" (
	"snapshot_id" bigint,
	"case_id" bigint,
	"in_degree" integer,
	"out_degree" integer,
	"pagerank" real,
	"betweenness" real,
	"hub_score" real,
	"authority_score" real,
	"eigenvector" real,
	CONSTRAINT "case_network_metric_pkey" PRIMARY KEY("snapshot_id","case_id")
);
CREATE TABLE "cle_v2"."case_party" (
	"case_id" bigint,
	"party_id" bigint,
	"role" text,
	"ordinal" smallint DEFAULT 1,
	CONSTRAINT "case_party_pkey" PRIMARY KEY("case_id","party_id","role","ordinal")
);
CREATE TABLE "cle_v2"."case_segment" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_segment_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint,
	"language" text,
	"segment_type" text,
	"segment_index" integer,
	"segment_text" text,
	"segment_hash" text,
	"embedding" vector(768),
	"embedding_model" text,
	"extractor_version" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "case_segment_case_id_segment_hash_key" UNIQUE("case_id","segment_hash")
);
CREATE TABLE "cle_v2"."case_summary_version" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_summary_version_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL,
	"language" text,
	"summary_text" text NOT NULL,
	"summary_embedding" vector(768),
	"embedding_model" text,
	"summarization_model" text,
	"segment_scope" text NOT NULL,
	"version_number" integer DEFAULT 1 NOT NULL,
	"is_current" boolean DEFAULT true NOT NULL,
	"generation_source" text NOT NULL,
	"rejected_at" timestamp with time zone,
	"rejection_reason" text,
	"parent_version_id" bigint,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."case_text" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_text_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL,
	"language" text NOT NULL,
	"fulltext" text,
	"summary" text,
	"summary_source" text,
	"fulltext_tsv" tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, COALESCE(fulltext, ''::text))) STORED,
	"summary_tsv" tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, COALESCE(summary, ''::text))) STORED,
	"summary_embedding" vector(768),
	"embedding_model" text,
	"source" text NOT NULL,
	"text_format" text,
	"missing_reasons" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"is_stub" boolean DEFAULT false NOT NULL,
	CONSTRAINT "case_text_case_id_language_source_key" UNIQUE("case_id","language","source")
);
CREATE TABLE "cle_v2"."cases" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cases_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"ecli" text CONSTRAINT "cases_ecli_key" UNIQUE,
	"item_id" text CONSTRAINT "cases_item_id_key" UNIQUE,
	"celex_id" text CONSTRAINT "cases_celex_id_key" UNIQUE,
	"title" text,
	"date_decision" date,
	"date_published" date,
	"court_id" bigint,
	"language_iso" text,
	"document_type_id" bigint,
	"procedure_type_id" bigint,
	"instance_id" bigint,
	"case_number" text,
	"importance" smallint,
	"is_landmark" boolean,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"sources" text[] NOT NULL
);
CREATE TABLE "cle_v2"."cjeu_ag_opinion" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cjeu_ag_opinion_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL CONSTRAINT "cjeu_ag_opinion_case_id_key" UNIQUE,
	"parent_case_id" bigint,
	"advocate_general" text,
	"opinion_uri" text,
	"delivered_date" date
);
CREATE TABLE "cle_v2"."cjeu_document" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cjeu_document_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL CONSTRAINT "cjeu_document_case_id_key" UNIQUE,
	"celex_id" text,
	"ecli" text,
	"sector" text,
	"case_number" text,
	"formation_id" bigint,
	"proc_type" text,
	"procedure_result" text,
	"date_lodged" date,
	"cellar_uri" text,
	"work_uri" text,
	"journal_refs" text,
	"erecueil_ref" text,
	"local_identifier" text,
	"dossier_uri" text,
	"dossier_parent_case_id" bigint,
	"citations_extra_info" text,
	"national_judgement_xml" text
);
CREATE TABLE "cle_v2"."cjeu_national_document" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cjeu_national_document_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL CONSTRAINT "cjeu_national_document_case_id_key" UNIQUE,
	"national_court_uri" text,
	"national_decision_internal_id" text,
	"national_parties_raw" text,
	"national_keywords" text,
	"national_reference_publication" text,
	"national_reference_publication_conclusion" text,
	"national_follow_up" text,
	"national_judgement_reference" text,
	"national_act_reference_national" text,
	"national_act_reference_international" text,
	"national_act_reference_european" text,
	"national_based_on_resource_legal" text
);
CREATE TABLE "cle_v2"."court" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."court_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "court_code_key" UNIQUE,
	"name" text,
	"level" text,
	"jurisdiction_id" bigint,
	"parent_court_id" bigint
);
CREATE TABLE "cle_v2"."court_formation" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."court_formation_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "court_formation_code_key" UNIQUE,
	"label" text,
	"judge_count" smallint
);
CREATE TABLE "cle_v2"."document_type" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."document_type_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "document_type_code_key" UNIQUE,
	"name" text
);
CREATE TABLE "cle_v2"."domain" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."domain_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"scheme" text,
	"name" text,
	"uri" text,
	"parent_id" bigint
);
CREATE TABLE "cle_v2"."domain_label" (
	"domain_id" bigint,
	"language" text,
	"label" text NOT NULL,
	CONSTRAINT "domain_label_pkey" PRIMARY KEY("domain_id","language")
);
CREATE TABLE "cle_v2"."echr_document" (
	"item_id" text PRIMARY KEY,
	"case_id" bigint NOT NULL,
	"language" text NOT NULL,
	"extractedappno" text,
	"docname" text,
	"doctype" text,
	"doctype_branch" text,
	"judgement_date" timestamp with time zone,
	"reference_date" timestamp with time zone,
	"article" text,
	"conclusion" text,
	"violation" text,
	"nonviolation" text,
	"respondent" text,
	"originating_body" integer,
	"represented_by" text,
	"published_by" text,
	"rules_of_court" text,
	"applicability" text,
	"separate_opinion" text,
	"issue" text,
	"importance" smallint,
	"rank" numeric,
	"scl" text,
	"external_sources" text,
	"judgement_year" integer GENERATED ALWAYS AS ((EXTRACT(year FROM (judgement_date AT TIME ZONE 'UTC'::text)))::integer) STORED,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."echr_document_appno" (
	"item_id" text,
	"appno" text,
	"source" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "echr_document_appno_pkey" PRIMARY KEY("item_id","appno","source")
);
CREATE TABLE "cle_v2"."echr_document_article" (
	"item_id" text,
	"kind" text,
	"article_code" text,
	"protocol" text,
	"raw" text,
	CONSTRAINT "echr_document_article_pkey" PRIMARY KEY("item_id","kind","article_code"),
	CONSTRAINT "echr_document_article_kind_check" CHECK ((kind = ANY (ARRAY['applied'::text, 'violation'::text, 'nonviolation'::text])))
);
CREATE TABLE "cle_v2"."echr_document_secondary_text" (
	"item_id" text PRIMARY KEY,
	"fulltext" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."echr_extractor_segments" (
	"item_id" text PRIMARY KEY,
	"parser_mode" text,
	"error" text,
	"procedure" text,
	"facts" text,
	"complaints" text,
	"law" text,
	"operative" text,
	"subject_matter" text,
	"court_assessment" text,
	"separate_opinion" text,
	"appendix" text,
	"num_sections" integer DEFAULT 0 NOT NULL,
	"segmented_at" timestamp with time zone DEFAULT now() NOT NULL,
	"extractor_version" text
);
CREATE TABLE "cle_v2"."instance" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."instance_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "instance_code_key" UNIQUE,
	"name" text
);
CREATE TABLE "cle_v2"."judge" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."judge_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"full_name" text,
	"aliases" text[],
	"court_id" bigint
);
CREATE TABLE "cle_v2"."jurisdiction" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."jurisdiction_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"iso_code" text CONSTRAINT "jurisdiction_iso_code_key" UNIQUE,
	"name" text,
	"type" text
);
CREATE TABLE "cle_v2"."language" (
	"iso_code" text PRIMARY KEY,
	"name" text
);
-- Seed for the FKs on case_text.language / cases.language_iso: the 24
-- official EU languages (ISO 639-1), covering CJEU/Cellar and ECHR/HUDOC
-- member-state languages as well as Rechtspraak's "nl".
INSERT INTO "cle_v2"."language" ("iso_code", "name") VALUES
	('bg', 'Bulgarian'),
	('hr', 'Croatian'),
	('cs', 'Czech'),
	('da', 'Danish'),
	('nl', 'Dutch'),
	('en', 'English'),
	('et', 'Estonian'),
	('fi', 'Finnish'),
	('fr', 'French'),
	('de', 'German'),
	('el', 'Greek'),
	('hu', 'Hungarian'),
	('ga', 'Irish'),
	('it', 'Italian'),
	('lv', 'Latvian'),
	('lt', 'Lithuanian'),
	('mt', 'Maltese'),
	('pl', 'Polish'),
	('pt', 'Portuguese'),
	('ro', 'Romanian'),
	('sk', 'Slovak'),
	('sl', 'Slovenian'),
	('es', 'Spanish'),
	('sv', 'Swedish')
ON CONFLICT ("iso_code") DO NOTHING;
CREATE TABLE "cle_v2"."legal_provision" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."legal_provision_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"legislation_id" bigint,
	"parent_id" bigint,
	"element_type" text,
	"article_label" text,
	"title" text,
	"paragraph" text,
	"text" text,
	"bwb_label_id" bigint,
	"lido_id" text CONSTRAINT "legal_provision_lido_id_key" UNIQUE,
	-- jc_id is NOT reliably unique in real LIDO data (distinct dated lido_id
	-- nodes for the same provision can share a jci1.3 reference); lido_id is
	-- the actual unique natural key here. Discovered when the first real
	-- lido_postgres-successor merge hit a UniqueViolation on this constraint.
	"jc_id" text,
	"effective_from" date,
	"effective_to" date,
	"snapshot_date" date
);
CREATE TABLE "cle_v2"."legislation" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."legislation_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"identifier" text,
	"scheme" text,
	"title" text,
	"jurisdiction_id" bigint,
	"document_type" text,
	"enacted_date" date,
	"lido_id" text CONSTRAINT "legislation_lido_id_key" UNIQUE,
	-- Same reasoning as legal_provision.jc_id: not reliably unique in real data.
	"jc_id" text,
	"snapshot_date" date
);
CREATE TABLE "cle_v2"."legislation_alias" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."legislation_alias_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"legislation_id" bigint,
	"alias" text,
	"source" text
);
CREATE TABLE "cle_v2"."lido_link" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."lido_link_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"source_case_id" bigint,
	"target_case_id" bigint,
	"source_ecli" text,
	"source_uri" text,
	"target_ecli" text,
	"target_uri" text,
	"target_provision_id" bigint,
	"link_type" text,
	"fetched_at" timestamp with time zone DEFAULT now()
);
CREATE TABLE "cle_v2"."migration_manifest" (
	"step" text PRIMARY KEY,
	"completed_at" timestamp with time zone DEFAULT now() NOT NULL,
	"rows_affected" bigint,
	"note" text
);
CREATE TABLE "cle_v2"."network_snapshot" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."network_snapshot_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"snapshot_date" date,
	"description" text,
	"node_count" integer,
	"edge_count" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."party" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."party_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"canonical_name" text,
	"aliases" text[],
	"role_class" text,
	"country_iso" text
);
CREATE TABLE "cle_v2"."procedure_type" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."procedure_type_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "procedure_type_code_key" UNIQUE,
	"name" text
);
CREATE TABLE "cle_v2"."rs_document" (
	"case_id" bigint PRIMARY KEY,
	"date_decision" date,
	"document_type" text,
	"instance" text,
	"domains" text[],
	"source" text DEFAULT 'Rechtspraak' NOT NULL,
	"jurisdiction_country" text DEFAULT 'NL' NOT NULL,
	"procedure_type" text,
	"url_publication" text,
	"legal_provisions" text[],
	"predecessor_successor_cases" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"date_published" date,
	"date_issued" date,
	"date_modified" timestamp with time zone,
	"title" text,
	"language" text,
	"access_rights" text,
	"zittingsplaats" text,
	"replaces_identifier" text,
	"creator_uri" text,
	"vindplaatsen" text[],
	"subject_uris" text[],
	"zaaknummer" text,
	"opendata_status" text DEFAULT 'public' NOT NULL,
	CONSTRAINT "rs_document_opendata_status_check" CHECK ((opendata_status = ANY (ARRAY['public'::text, 'depublicated'::text])))
);
CREATE TABLE "cle_v2"."rs_document_external_authority" (
	"case_id" bigint,
	"kind" text DEFAULT 'other' NOT NULL,
	"name" text NOT NULL,
	"article" text,
	"raw" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "rs_document_external_authority_pkey" PRIMARY KEY("case_id","raw")
);
CREATE TABLE "cle_v2"."rs_document_formal_relation" (
	"case_id" bigint,
	"target_ecli" text,
	"target_identifier" text,
	"relation_type" text DEFAULT 'unknown',
	"aanleg" text DEFAULT 'unknown',
	"name" text,
	"disposition" text,
	"gevolg" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "rs_document_formal_relation_pkey" PRIMARY KEY("case_id","target_identifier","relation_type","aanleg")
);
CREATE TABLE "cle_v2"."rs_document_publication" (
	"case_id" bigint,
	"raw" text,
	"kind" text DEFAULT 'other' NOT NULL,
	"journal_abbr" text,
	"year" integer,
	"locator" text,
	"annotator" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "rs_document_publication_pkey" PRIMARY KEY("case_id","raw")
);
CREATE TABLE "cle_v2"."search_query_log" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."search_query_log_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"user_id" text,
	"raw_query" text,
	"parsed_intent" jsonb,
	"filters" jsonb,
	"strategy" text,
	"result_count" integer,
	"clicked_case_ids" text[],
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX "case_citation_idx_relation_type" ON "cle_v2"."case_citation" ("relation_type");
CREATE INDEX "case_citation_idx_source" ON "cle_v2"."case_citation" ("source_case_id");
CREATE INDEX "case_citation_idx_source_target" ON "cle_v2"."case_citation" ("source_case_id","target_case_id");
CREATE INDEX "case_citation_idx_target" ON "cle_v2"."case_citation" ("target_case_id");
CREATE INDEX "case_citation_idx_target_celex_raw" ON "cle_v2"."case_citation" ("target_celex_raw");
CREATE INDEX "case_citation_idx_target_ecli_raw" ON "cle_v2"."case_citation" ("target_ecli_raw");
CREATE INDEX "case_citation_idx_weight" ON "cle_v2"."case_citation" ("weight");
CREATE UNIQUE INDEX "case_citation_uk_resolved" ON "cle_v2"."case_citation" ("source_case_id","target_case_id","relation_type","source_dataset") WHERE "target_case_id" IS NOT NULL;
CREATE UNIQUE INDEX "case_citation_uk_unresolved_celex" ON "cle_v2"."case_citation" ("source_case_id","target_celex_raw","relation_type","source_dataset") WHERE "target_case_id" IS NULL AND "target_celex_raw" IS NOT NULL;
CREATE UNIQUE INDEX "case_citation_uk_unresolved_ecli" ON "cle_v2"."case_citation" ("source_case_id","target_ecli_raw","relation_type","source_dataset") WHERE "target_case_id" IS NULL AND "target_ecli_raw" IS NOT NULL;
CREATE INDEX "case_domain_idx_domain_id" ON "cle_v2"."case_domain" ("domain_id");
CREATE INDEX "case_entity_idx_case_id" ON "cle_v2"."case_entity" ("case_id");
CREATE INDEX "case_judge_idx_case_id" ON "cle_v2"."case_judge" ("case_id");
CREATE INDEX "case_judge_idx_judge_id" ON "cle_v2"."case_judge" ("judge_id");
CREATE INDEX "case_law_reference_idx_case_id" ON "cle_v2"."case_law_reference" ("case_id");
CREATE INDEX "case_law_reference_idx_legislation" ON "cle_v2"."case_law_reference" ("legislation_id");
CREATE INDEX "case_law_reference_idx_provision" ON "cle_v2"."case_law_reference" ("provision_id");
CREATE INDEX "case_law_reference_idx_raw" ON "cle_v2"."case_law_reference" ("raw_scheme","raw_resource");
CREATE INDEX "case_law_reference_idx_raw_label" ON "cle_v2"."case_law_reference" ("raw_label_id");
-- Partial, as in caselaw-coolify 0001 (one key per resolution state), so local
-- loads see the same arbiters as db-dev and production: plain indexes here
-- made a provision row collide with another provision of the same act under
-- _uk_legislation, which the deployed database allows.
CREATE UNIQUE INDEX "case_law_reference_uk_legislation" ON "cle_v2"."case_law_reference" ("case_id","legislation_id","role","source_dataset") WHERE "provision_id" IS NULL AND "legislation_id" IS NOT NULL AND "raw_resource" IS NULL;
CREATE UNIQUE INDEX "case_law_reference_uk_provision" ON "cle_v2"."case_law_reference" ("case_id","provision_id","role","source_dataset") WHERE "provision_id" IS NOT NULL AND "raw_resource" IS NULL;
CREATE UNIQUE INDEX "case_law_reference_uk_raw" ON "cle_v2"."case_law_reference" ("case_id","raw_scheme","raw_resource",COALESCE(raw_subdivision, ''::text),"role","source_dataset") WHERE "provision_id" IS NULL AND "legislation_id" IS NULL AND "raw_resource" IS NOT NULL;
CREATE INDEX "case_network_metric_idx_case" ON "cle_v2"."case_network_metric" ("case_id");
CREATE INDEX "case_party_idx_party" ON "cle_v2"."case_party" ("party_id");
CREATE INDEX "case_segment_idx_case_id" ON "cle_v2"."case_segment" ("case_id");
CREATE INDEX "case_summary_version_idx_case" ON "cle_v2"."case_summary_version" ("case_id");
CREATE UNIQUE INDEX "case_summary_version_uk_current" ON "cle_v2"."case_summary_version" ("case_id","segment_scope","summarization_model");
CREATE INDEX "case_text_idx_case_id" ON "cle_v2"."case_text" ("case_id");
CREATE INDEX "case_text_idx_fulltext_tsv" ON "cle_v2"."case_text" USING gin ("fulltext_tsv");
CREATE INDEX "case_text_idx_stub" ON "cle_v2"."case_text" ("case_id");
CREATE INDEX "case_text_idx_summary_embedding" ON "cle_v2"."case_text" USING hnsw ("summary_embedding" vector_cosine_ops);
CREATE INDEX "case_text_idx_summary_tsv" ON "cle_v2"."case_text" USING gin ("summary_tsv");
CREATE INDEX "case_idx_case_number" ON "cle_v2"."cases" ("case_number");
CREATE INDEX "case_idx_case_number_trgm" ON "cle_v2"."cases" USING gin ("case_number" gin_trgm_ops);
CREATE INDEX "case_idx_court" ON "cle_v2"."cases" ("court_id");
CREATE INDEX "case_idx_date_decision" ON "cle_v2"."cases" ("date_decision");
CREATE INDEX "case_idx_date_ecli" ON "cle_v2"."cases" ("date_decision","ecli");
CREATE INDEX "case_idx_ecli" ON "cle_v2"."cases" ("ecli");
CREATE INDEX "case_idx_importance" ON "cle_v2"."cases" ("importance");
CREATE INDEX "case_idx_item_id" ON "cle_v2"."cases" ("item_id");
CREATE INDEX "case_idx_sources" ON "cle_v2"."cases" USING gin ("sources");
CREATE INDEX "case_idx_title_trgm" ON "cle_v2"."cases" USING gin ("title" gin_trgm_ops);
CREATE INDEX "cases_idx_case_number_btree" ON "cle_v2"."cases" ("case_number");
CREATE INDEX "echr_document_idx_case_lang" ON "cle_v2"."echr_document" ("case_id","language");
CREATE INDEX "echr_document_idx_docname_trgm" ON "cle_v2"."echr_document" USING gin ("docname" gin_trgm_ops);
CREATE INDEX "echr_document_idx_doctype" ON "cle_v2"."echr_document" ("doctype");
CREATE INDEX "echr_document_idx_doctype_branch" ON "cle_v2"."echr_document" ("doctype_branch");
CREATE INDEX "echr_document_idx_issue_trgm" ON "cle_v2"."echr_document" USING gin ("issue" gin_trgm_ops);
CREATE INDEX "echr_document_idx_judgement_date" ON "cle_v2"."echr_document" ("judgement_date");
CREATE INDEX "echr_document_idx_judgement_year" ON "cle_v2"."echr_document" ("judgement_year");
CREATE INDEX "echr_document_idx_originating_body" ON "cle_v2"."echr_document" ("originating_body");
CREATE INDEX "echr_document_idx_reference_date" ON "cle_v2"."echr_document" ("reference_date");
CREATE INDEX "echr_document_appno_idx_appno" ON "cle_v2"."echr_document_appno" ("appno");
CREATE INDEX "echr_document_appno_idx_source" ON "cle_v2"."echr_document_appno" ("source");
CREATE INDEX "echr_document_article_idx_filter" ON "cle_v2"."echr_document_article" ("kind","article_code");
CREATE INDEX "echr_extractor_segments_idx_num_sections" ON "cle_v2"."echr_extractor_segments" ("num_sections");
CREATE INDEX "echr_extractor_segments_idx_parser" ON "cle_v2"."echr_extractor_segments" ("parser_mode");
CREATE INDEX "legal_provision_idx_bwb_label" ON "cle_v2"."legal_provision" ("bwb_label_id");
CREATE INDEX "legal_provision_idx_lookup" ON "cle_v2"."legal_provision" ("legislation_id",lower(article_label),"element_type");
CREATE INDEX "legislation_idx_scheme_identifier" ON "cle_v2"."legislation" ("scheme","identifier");
CREATE INDEX "legislation_alias_idx_alias_lower" ON "cle_v2"."legislation_alias" (lower(alias));
CREATE INDEX "legislation_alias_idx_alias_trgm" ON "cle_v2"."legislation_alias" USING gin ("alias" gin_trgm_ops);
-- No unique constraint existed on this table before (safe to add now: table has
-- zero rows/writers). Needed by the lido_postgres -> cle_v2 merge (airflow/dags/lido/)
-- to upsert idempotently on reruns.
CREATE UNIQUE INDEX "legislation_alias_uk" ON "cle_v2"."legislation_alias" ("legislation_id", "alias");
CREATE INDEX "lido_link_idx_source_case" ON "cle_v2"."lido_link" ("source_case_id");
CREATE INDEX "lido_link_idx_target_case" ON "cle_v2"."lido_link" ("target_case_id");
CREATE INDEX "rs_document_idx_date_decision" ON "cle_v2"."rs_document" ("date_decision");
CREATE INDEX "rs_document_idx_date_issued" ON "cle_v2"."rs_document" ("date_issued");
CREATE INDEX "rs_document_idx_date_modified" ON "cle_v2"."rs_document" ("date_modified");
CREATE INDEX "rs_document_idx_domains_gin" ON "cle_v2"."rs_document" USING gin ("domains");
CREATE INDEX "rs_document_publication_idx_journal" ON "cle_v2"."rs_document_publication" ("journal_abbr");
ALTER TABLE "cle_v2"."case_citation" ADD CONSTRAINT "fk_case_citation_context" FOREIGN KEY ("context_segment_id") REFERENCES "cle_v2"."case_segment"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."case_citation" ADD CONSTRAINT "fk_case_citation_source" FOREIGN KEY ("source_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_citation" ADD CONSTRAINT "fk_case_citation_target" FOREIGN KEY ("target_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."case_citation_counts" ADD CONSTRAINT "fk_case_citation_counts" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_cluster" ADD CONSTRAINT "fk_case_cluster_snapshot" FOREIGN KEY ("snapshot_id") REFERENCES "cle_v2"."network_snapshot"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_cluster_membership" ADD CONSTRAINT "fk_case_cluster_membership_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_cluster_membership" ADD CONSTRAINT "fk_case_cluster_membership_clus" FOREIGN KEY ("cluster_id") REFERENCES "cle_v2"."case_cluster"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_domain" ADD CONSTRAINT "fk_case_domain_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_domain" ADD CONSTRAINT "fk_case_domain_domain" FOREIGN KEY ("domain_id") REFERENCES "cle_v2"."domain"("id");
ALTER TABLE "cle_v2"."case_entity" ADD CONSTRAINT "fk_case_entity_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_judge" ADD CONSTRAINT "fk_case_judge_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_judge" ADD CONSTRAINT "fk_case_judge_judge" FOREIGN KEY ("judge_id") REFERENCES "cle_v2"."judge"("id");
ALTER TABLE "cle_v2"."case_law_reference" ADD CONSTRAINT "fk_case_law_reference_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_law_reference" ADD CONSTRAINT "fk_case_law_reference_leg" FOREIGN KEY ("legislation_id") REFERENCES "cle_v2"."legislation"("id");
ALTER TABLE "cle_v2"."case_law_reference" ADD CONSTRAINT "fk_case_law_reference_prov" FOREIGN KEY ("provision_id") REFERENCES "cle_v2"."legal_provision"("id");
ALTER TABLE "cle_v2"."case_network_metric" ADD CONSTRAINT "fk_case_network_metric_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_network_metric" ADD CONSTRAINT "fk_case_network_metric_snapshot" FOREIGN KEY ("snapshot_id") REFERENCES "cle_v2"."network_snapshot"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_party" ADD CONSTRAINT "fk_case_party_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_party" ADD CONSTRAINT "fk_case_party_party" FOREIGN KEY ("party_id") REFERENCES "cle_v2"."party"("id");
ALTER TABLE "cle_v2"."case_segment" ADD CONSTRAINT "fk_case_segment_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_segment" ADD CONSTRAINT "fk_case_segment_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."case_summary_version" ADD CONSTRAINT "fk_case_summary_version_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_summary_version" ADD CONSTRAINT "fk_case_summary_version_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."case_summary_version" ADD CONSTRAINT "fk_case_summary_version_parent" FOREIGN KEY ("parent_version_id") REFERENCES "cle_v2"."case_summary_version"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."case_text" ADD CONSTRAINT "fk_case_text_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_text" ADD CONSTRAINT "fk_case_text_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_court" FOREIGN KEY ("court_id") REFERENCES "cle_v2"."court"("id");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_document_type" FOREIGN KEY ("document_type_id") REFERENCES "cle_v2"."document_type"("id");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_instance" FOREIGN KEY ("instance_id") REFERENCES "cle_v2"."instance"("id");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_language" FOREIGN KEY ("language_iso") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_procedure_type" FOREIGN KEY ("procedure_type_id") REFERENCES "cle_v2"."procedure_type"("id");
ALTER TABLE "cle_v2"."cjeu_ag_opinion" ADD CONSTRAINT "fk_cjeu_ag_opinion_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."cjeu_ag_opinion" ADD CONSTRAINT "fk_cjeu_ag_opinion_parent" FOREIGN KEY ("parent_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."cjeu_document" ADD CONSTRAINT "fk_cjeu_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."cjeu_document" ADD CONSTRAINT "fk_cjeu_document_dossier" FOREIGN KEY ("dossier_parent_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."cjeu_document" ADD CONSTRAINT "fk_cjeu_document_formation" FOREIGN KEY ("formation_id") REFERENCES "cle_v2"."court_formation"("id");
ALTER TABLE "cle_v2"."cjeu_national_document" ADD CONSTRAINT "fk_cjeu_national_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."court" ADD CONSTRAINT "fk_court_jurisdiction" FOREIGN KEY ("jurisdiction_id") REFERENCES "cle_v2"."jurisdiction"("id");
ALTER TABLE "cle_v2"."court" ADD CONSTRAINT "fk_court_parent_court" FOREIGN KEY ("parent_court_id") REFERENCES "cle_v2"."court"("id");
ALTER TABLE "cle_v2"."domain" ADD CONSTRAINT "fk_domain_parent" FOREIGN KEY ("parent_id") REFERENCES "cle_v2"."domain"("id");
ALTER TABLE "cle_v2"."domain_label" ADD CONSTRAINT "fk_domain_label_domain" FOREIGN KEY ("domain_id") REFERENCES "cle_v2"."domain"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."domain_label" ADD CONSTRAINT "fk_domain_label_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."echr_document" ADD CONSTRAINT "fk_echr_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_document" ADD CONSTRAINT "fk_echr_document_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."echr_document_appno" ADD CONSTRAINT "fk_echr_document_appno_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_document_article" ADD CONSTRAINT "fk_echr_document_article_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_document_secondary_text" ADD CONSTRAINT "fk_echr_document_secondary_text_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_extractor_segments" ADD CONSTRAINT "fk_echr_extractor_segments_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."judge" ADD CONSTRAINT "fk_judge_court" FOREIGN KEY ("court_id") REFERENCES "cle_v2"."court"("id");
ALTER TABLE "cle_v2"."legal_provision" ADD CONSTRAINT "fk_legal_provision" FOREIGN KEY ("legislation_id") REFERENCES "cle_v2"."legislation"("id");
ALTER TABLE "cle_v2"."legal_provision" ADD CONSTRAINT "fk_legal_provision_parent" FOREIGN KEY ("parent_id") REFERENCES "cle_v2"."legal_provision"("id");
ALTER TABLE "cle_v2"."legislation" ADD CONSTRAINT "fk_legislation_jurisdiction" FOREIGN KEY ("jurisdiction_id") REFERENCES "cle_v2"."jurisdiction"("id");
ALTER TABLE "cle_v2"."legislation_alias" ADD CONSTRAINT "fk_legislation_alias" FOREIGN KEY ("legislation_id") REFERENCES "cle_v2"."legislation"("id");
ALTER TABLE "cle_v2"."lido_link" ADD CONSTRAINT "fk_lido_link_source_case" FOREIGN KEY ("source_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."lido_link" ADD CONSTRAINT "fk_lido_link_target_case" FOREIGN KEY ("target_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."lido_link" ADD CONSTRAINT "fk_lido_link_target_provision" FOREIGN KEY ("target_provision_id") REFERENCES "cle_v2"."legal_provision"("id");
ALTER TABLE "cle_v2"."party" ADD CONSTRAINT "fk_party_country" FOREIGN KEY ("country_iso") REFERENCES "cle_v2"."jurisdiction"("iso_code");
ALTER TABLE "cle_v2"."rs_document" ADD CONSTRAINT "fk_rs_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."rs_document_external_authority" ADD CONSTRAINT "fk_rs_document_ext_authority" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."rs_document"("case_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."rs_document_formal_relation" ADD CONSTRAINT "fk_rs_document_formal_source" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."rs_document"("case_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."rs_document_formal_relation" ADD CONSTRAINT "fk_rs_document_formal_target" FOREIGN KEY ("target_ecli") REFERENCES "cle_v2"."cases"("ecli") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."rs_document_publication" ADD CONSTRAINT "fk_rs_document_publication_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."rs_document"("case_id") ON DELETE CASCADE;
-- Reconstructed: not captured anywhere before this fix (not in schema.sql, not
-- in git history, not in application code) despite being called by
-- rs_v_document_law_reference below. wetten.overheid.nl/linkeddata.overheid.nl
-- URLs need a locale-independent YYYY-MM-DD segment, which is what this
-- provides; to_char (not date::text) makes that independent of DateStyle.
CREATE OR REPLACE FUNCTION "cle_v2"."rs_date_to_iso"("d" date)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT to_char(d, 'YYYY-MM-DD');
$$;
CREATE VIEW "cle_v2"."case_text_canonical" AS (SELECT DISTINCT ON (case_id, language) id, case_id, language, fulltext, summary, summary_source, fulltext_tsv, summary_tsv, summary_embedding, embedding_model, source, text_format, missing_reasons, created_at, updated_at FROM cle_v2.case_text t ORDER BY case_id, language, ( CASE source WHEN 'RECHTSPRAAK'::text THEN 1 WHEN 'HUDOC'::text THEN 2 WHEN 'INFOCURIA_BLOB_HTML'::text THEN 3 WHEN 'CELLAR_ITEM'::text THEN 4 ELSE 5 END), id);
CREATE VIEW "cle_v2"."echr_v_document_with_text" AS (SELECT d.item_id, d.case_id, d.language, d.extractedappno, d.docname, d.doctype, d.doctype_branch, d.judgement_date, d.reference_date, d.article, d.conclusion, d.violation, d.nonviolation, d.respondent, d.originating_body, d.represented_by, d.published_by, d.rules_of_court, d.applicability, d.separate_opinion, d.issue, d.importance, d.rank, d.scl, d.external_sources, d.judgement_year, d.created_at, d.updated_at, t.fulltext, t.fulltext_tsv FROM cle_v2.echr_document d LEFT JOIN cle_v2.case_text_canonical t ON t.case_id = d.case_id AND t.language = d.language);
CREATE VIEW "cle_v2"."echr_v_judgments_decisions" AS (SELECT item_id, case_id, language, extractedappno, docname, doctype, doctype_branch, judgement_date, reference_date, article, conclusion, violation, nonviolation, respondent, originating_body, represented_by, published_by, rules_of_court, applicability, separate_opinion, issue, importance, rank, scl, external_sources, judgement_year, created_at, updated_at FROM cle_v2.echr_document WHERE doctype ~~* '%JUD%'::text OR doctype ~~* '%DEC%'::text);
CREATE VIEW "cle_v2"."rs_v_document_law_reference" AS (SELECT r.case_id, c.ecli, r.raw_resource AS bwb_resource, COALESCE(r.raw_subdivision, ''::text) AS article, r.version_date, r.raw_label_id AS bwb_label_id, r.source_dataset AS source, r.raw_reference AS opschrift, ((('http://wetten.overheid.nl/id/'::text || r.raw_resource) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text)) || '/0'::text AS legal_provision_url, CASE WHEN r.raw_label_id IS NULL THEN NULL::text ELSE (((((('http://linkeddata.overheid.nl/terms/bwb/id/'::text || r.raw_resource) || '/'::text) || r.raw_label_id::text) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text)) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text) END AS legal_provision_url_lido FROM cle_v2.case_law_reference r JOIN cle_v2.cases c ON c.id = r.case_id WHERE r.raw_scheme = 'bwb'::text);
CREATE VIEW "cle_v2"."rs_v_document_legal_provisions" AS (SELECT DISTINCT c.ecli, lr.raw_reference AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lr.raw_reference, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lp.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legal_provision lp ON lp.bwb_label_id = lr.raw_label_id WHERE lr.raw_scheme = 'bwb'::text AND lr.raw_label_id IS NOT NULL AND NULLIF(lp.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lp.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource JOIN cle_v2.legal_provision lp ON lp.legislation_id = lg.id AND lower(lp.article_label) = lower(lr.raw_subdivision) AND lp.element_type = 'artikel'::text WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lp.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lg.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, (lg.title || ', Artikel '::text) || lr.raw_subdivision AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL AND NULLIF(lr.raw_subdivision, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, (lg.title || ', Bijlage '::text) || lr.raw_subdivision AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL AND NULLIF(lr.raw_subdivision, ''::text) IS NOT NULL AND lr.raw_reference ~~* '%bijlage%'::text);
CREATE VIEW "cle_v2"."rs_v_document_with_text" AS (SELECT d.case_id, d.date_decision, d.document_type, d.instance, d.domains, d.source, d.jurisdiction_country, d.procedure_type, d.url_publication, d.legal_provisions, d.predecessor_successor_cases, d.created_at, d.updated_at, d.date_published, d.date_issued, d.date_modified, d.title, d.language, d.access_rights, d.zittingsplaats, d.replaces_identifier, d.creator_uri, d.vindplaatsen, d.subject_uris, d.zaaknummer, d.opendata_status, t.summary, t.fulltext, t.fulltext_tsv FROM cle_v2.rs_document d LEFT JOIN cle_v2.case_text_canonical t ON t.case_id = d.case_id AND t.language = 'nl'::text);

-- =============================================================================
-- Mirrored from MaastrichtU-BISS/caselaw-coolify db/migrations (the deployed
-- schema): 0008_case_text_document_kind, 0009_cross_dataset_links,
-- 0010_case_citation_link_indexes, 0011_legislation_external_keys,
-- 0012_case_law_reference_provenance, 0013_case_timeline_view and
-- 0014_case_law_reference_indexes. Keep in step with those files.
-- =============================================================================

-- ---- 0008_case_text_document_kind.sql ----
-- What document a case_text row holds, not just where it was fetched from.
--
-- `source` records the fetch route (CELLAR_ITEM, INFOCURIA_BLOB_HTML, ...),
-- which says nothing about what the text is. CJEU rows have mixed the
-- decision itself with abstracts of it (CELLAR `_SUM` summaries, `_INF`
-- information sheets, Official Journal notices) and with texts of other
-- documents filed under the wrong case (an Advocate General's opinion in a
-- judgment's slot). All of them looked like "the fulltext" of the case.
--
-- document_kind:
--   judgment | order | opinion | ruling | decision | other
--                  the decision itself (same vocabulary as document_type.code)
--   extract        a partial text of the decision (CELLAR `_EXT`)
--   summary        a summary of the decision (CELLAR `_SUM`, `_RES`)
--   information    an information sheet (CELLAR `_INF`)
--   oj_notice      the decision's Official Journal notice
--   misfiled       another document's text filed under this case; kept for
--                  provenance, never served as this case's text
--   NULL           not classified (Rechtspraak, HUDOC, rows loaded before
--                  classification); treated like the decision itself
-- document_celex: CELEX of the work the text was taken from, when known.

ALTER TABLE "cle_v2"."case_text"
    ADD COLUMN IF NOT EXISTS "document_kind" text,
    ADD COLUMN IF NOT EXISTS "document_celex" text;

ALTER TABLE "cle_v2"."case_text"
    DROP CONSTRAINT IF EXISTS "case_text_document_kind_check";
ALTER TABLE "cle_v2"."case_text"
    ADD CONSTRAINT "case_text_document_kind_check" CHECK (
        "document_kind" IN (
            'judgment', 'order', 'opinion', 'ruling', 'decision', 'other',
            'extract', 'summary', 'information', 'oj_notice', 'misfiled'
        )
    ) NOT VALID;

COMMENT ON COLUMN "cle_v2"."case_text"."document_kind" IS
    'What the text is: the decision itself (judgment, order, opinion, ruling, decision, other), an extract, summary, information sheet or OJ notice of it, or misfiled (another document''s text). NULL = not classified.';
COMMENT ON COLUMN "cle_v2"."case_text"."document_celex" IS
    'CELEX of the work the text was taken from, when known.';

-- One text per (case, language): the decision itself before extracts before
-- abstracts; within a kind, a non-empty text first, then the origin source
-- (Rechtspraak, HUDOC), then CELLAR, which is keyed by the document's own
-- CELEX, before InfoCuria. Misfiled texts are never served.
CREATE OR REPLACE VIEW "cle_v2"."case_text_canonical" AS
SELECT DISTINCT ON (t."case_id", t."language") t.*
FROM "cle_v2"."case_text" t
WHERE t."document_kind" IS DISTINCT FROM 'misfiled'
ORDER BY t."case_id", t."language",
         CASE
             WHEN t."document_kind" IN ('summary', 'information', 'oj_notice') THEN 2
             WHEN t."document_kind" = 'extract' THEN 1
             ELSE 0
         END,
         (t."fulltext" IS NULL OR btrim(t."fulltext") = ''),
         CASE t."source"
             WHEN 'RECHTSPRAAK' THEN 1
             WHEN 'HUDOC' THEN 2
             WHEN 'CELLAR_ITEM' THEN 3
             WHEN 'INFOCURIA_BLOB_HTML' THEN 4
             ELSE 5
         END,
         t."id";

-- ---- 0009_cross_dataset_links.sql ----
-- Cross-dataset links: provenance, identifiers and the tables later phases fill.
--
-- Design: cjeu-migration docs/LINKING_DESIGN.md (Phase 1 of
-- docs/CROSS_DATASET_ROADMAP.md). Strictly additive:
--
--   * case_citation gains four nullable columns (no default, so existing rows
--     are not rewritten) and two NOT VALID checks on them (no scan of existing
--     rows; enforced for new and updated rows).
--   * Everything else is a new, empty table or a function nothing calls yet.
--     None of it feeds a count or an API response.
--
-- Lock order: the new tables that reference cases, case_text and case_segment
-- come first; the ALTER TABLE on case_citation (ACCESS EXCLUSIVE, held to the
-- end of the file) and the tables that reference case_citation come last, so
-- API reads of case_citation are never queued behind this file waiting for a
-- lock on another table. Nothing here scans or rewrites case_citation.
--
-- Indexes on case_citation itself are in 0010: built here, they would scan
-- case_citation while this file holds ACCESS EXCLUSIVE on it.
--
-- Before applying in production, check that none of the new table names exist
-- yet in the schema (CREATE TABLE IF NOT EXISTS would silently keep an older
-- definition).

-- (migration only) SET LOCAL lock_timeout = '5s';

-- ---------------------------------------------------------------------------
-- case_identifier: every identifier a case is cited by (R1.2)
-- ---------------------------------------------------------------------------
-- Not unique on (scheme, value_normalized): a CJEU case number belongs to the
-- judgment, its orders and the Advocate General's opinion, an application
-- number to several ECtHR documents. Extractors choose among them and record
-- how in case_citation.match_method / confidence. value_normalized follows
-- case-law-explorer data_extraction/linking/identifiers.py.

CREATE TABLE IF NOT EXISTS "cle_v2"."case_identifier" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "scheme" text NOT NULL,                 -- ecli | ljn | celex | cjeu_case_number | echr_appno | nl_zaaknummer | cellar_dossier_uuid
    "value" text NOT NULL,                  -- as found
    "value_normalized" text NOT NULL,
    "source" text NOT NULL,                 -- where it was found, e.g. cjeu_document.case_number, cellar_joins, echr_document_appno
    "is_primary" boolean DEFAULT false NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "fk_case_identifier_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_identifier_uk"
    ON "cle_v2"."case_identifier" ("case_id", "scheme", "value_normalized");
CREATE INDEX IF NOT EXISTS "case_identifier_idx_lookup"
    ON "cle_v2"."case_identifier" ("scheme", "value_normalized");
CREATE INDEX IF NOT EXISTS "case_identifier_idx_value_trgm"
    ON "cle_v2"."case_identifier" USING gin ("value_normalized" gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- What each relation type and each source dataset is (documentation lookups)
-- ---------------------------------------------------------------------------
-- No foreign keys: existing rows stay as they are. Nothing reads these tables
-- until the count and API guard (a later, separately approved change), which
-- first registers every dataset and relation type present in production, read
-- from production at that time, keeping today's datasets counted so it changes
-- no number on its own. Relation types are seeded here only where their
-- meaning is known; `counted` matters only once correct counts (R1.4) land.

CREATE TABLE IF NOT EXISTS "cle_v2"."citation_relation_type" (
    "code" text NOT NULL,
    "description" text NOT NULL,
    "is_citation" boolean NOT NULL,         -- a decision relying on another decision
    "is_inverse" boolean DEFAULT false NOT NULL,  -- a citation stored from the cited side (Cellar cited_by)
    "is_identity" boolean DEFAULT false NOT NULL, -- the same decision under another identifier
    "counted" boolean NOT NULL,             -- for citation counts once correct counts (R1.4) land
    "active_in_api" boolean DEFAULT true NOT NULL,
    PRIMARY KEY ("code")
);

CREATE TABLE IF NOT EXISTS "cle_v2"."citation_source_dataset" (
    "code" text NOT NULL,
    "description" text NOT NULL,
    "corpus" text,                          -- RS | CJEU | ECHR | cross
    "counted" boolean DEFAULT false NOT NULL,
    "active_in_api" boolean DEFAULT false NOT NULL,
    PRIMARY KEY ("code")
);

INSERT INTO "cle_v2"."citation_relation_type"
    ("code", "description", "is_citation", "is_inverse", "is_identity", "counted", "active_in_api")
VALUES
    ('cites', 'The source decision cites the target decision.', true, false, false, true, true),
    ('cited_by', 'A citation stored from the cited side: the target decision cites the source (Cellar).', true, true, false, false, true),
    ('joins', 'Joined cases (Cellar).', false, false, false, false, true),
    ('is_about_concept', 'A subject-matter concept, not a decision (Cellar).', false, false, false, false, false),
    ('subject_to_appeal', 'Points forward in time: the source decision was appealed in the target case (Cellar).', false, false, false, false, true),
    ('reexamined_by', 'Points forward in time: the source decision was reviewed in the target case (Cellar).', false, false, false, false, true),
    ('referred_for_preliminary_ruling', 'Reference for a preliminary ruling (Cellar).', false, false, false, false, true),
    ('interprets_judgement', 'Interpretation of an earlier judgment (Cellar); a procedure, not a precedent citation.', false, false, false, false, true),
    ('logical_successor_of', 'Successor document (Cellar).', false, false, false, false, true),
    ('replaced_by', 'Rechtspraak formal relation; across courts mostly an identity alias (an ECLI:NL copy of a foreign decision).', false, false, true, false, false),
    ('preliminary_reference', 'A national court''s referral to the CJEU ruling that answers it.', false, false, false, false, true),
    ('national_follow_up', 'A national decision given after a CJEU ruling, to that ruling (procedural; a text citation is a separate cites row).', false, false, false, false, true),
    ('opinion_of', 'An Advocate General''s opinion to the judgment it was delivered in.', false, false, false, false, true),
    ('appeal_of', 'A CJEU appeal judgment to the General Court decision under appeal.', false, false, false, false, true),
    ('earlier_instance', 'A decision to an earlier decision in the same national proceedings.', false, false, false, false, true),
    ('cites_in_domestic_law', 'An ECtHR judgment refers to the decision only where it reports the domestic proceedings or law (decision D4, pending).', false, false, false, false, true)
ON CONFLICT ("code") DO NOTHING;

-- ---------------------------------------------------------------------------
-- Other cited authorities (Phase 4): parliamentary papers, policy rules,
-- EU preparatory acts, foreign and EFTA courts, treaty bodies, literature
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "cle_v2"."authority_document" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "kind" text NOT NULL,                   -- nl_parliamentary_paper | nl_policy_rule | eu_preparatory_act | national_court_decision | efta_court | un_treaty_body | coe_body | literature
    "identifier" text,                      -- extractors give documents without a structured identifier a synthetic one
    "identifier_scheme" text,
    "title" text,
    "issuer" text,
    "date" date,
    "url" text,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "authority_document_uk" ON "cle_v2"."authority_document"
    ("kind", COALESCE("identifier_scheme", ''), "identifier") WHERE "identifier" IS NOT NULL;

CREATE TABLE IF NOT EXISTS "cle_v2"."case_authority_reference" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "authority_document_id" bigint,
    "raw_reference" text NOT NULL,
    "pinpoint" text,
    "case_text_id" bigint,
    "text_field" text,
    "language" text,
    "char_start" int,
    "char_end" int,
    "context" text,
    "context_segment_id" bigint,
    "source_dataset" text NOT NULL,
    "extractor_version" text NOT NULL,
    "match_method" text,
    "confidence" real,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "case_authority_reference_confidence_check"
        CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1),
    CONSTRAINT "case_authority_reference_offsets_check"
        CHECK ("char_start" IS NULL OR "char_end" IS NULL OR ("char_start" >= 0 AND "char_end" >= "char_start")),
    CONSTRAINT "fk_case_authority_reference_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE,
    CONSTRAINT "fk_case_authority_reference_document" FOREIGN KEY ("authority_document_id")
        REFERENCES "cle_v2"."authority_document" ("id") ON DELETE SET NULL,
    CONSTRAINT "fk_case_authority_reference_case_text" FOREIGN KEY ("case_text_id")
        REFERENCES "cle_v2"."case_text" ("id") ON DELETE SET NULL,
    CONSTRAINT "fk_case_authority_reference_segment" FOREIGN KEY ("context_segment_id")
        REFERENCES "cle_v2"."case_segment" ("id") ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_authority_reference_uk" ON "cle_v2"."case_authority_reference"
    ("case_id", md5("raw_reference"), COALESCE("text_field", ''), COALESCE("language", ''),
     COALESCE("char_start", -1), "source_dataset");
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_document" ON "cle_v2"."case_authority_reference"
    ("authority_document_id") WHERE "authority_document_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_case_text" ON "cle_v2"."case_authority_reference"
    ("case_text_id") WHERE "case_text_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_segment" ON "cle_v2"."case_authority_reference"
    ("context_segment_id") WHERE "context_segment_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_dataset" ON "cle_v2"."case_authority_reference"
    ("source_dataset");

-- ---------------------------------------------------------------------------
-- Outcomes and status (Phase 5)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "cle_v2"."case_outcome" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "scope" text DEFAULT 'overall' NOT NULL, -- overall | article
    "article" text,                         -- ECtHR: '3', '8', 'P1-1'
    "outcome" text NOT NULL,                -- violation | no_violation | dismissed | upheld | quashed | inadmissible | annulled | answered | ...
    "raw_value" text,
    "source_dataset" text NOT NULL,
    "extractor_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "fk_case_outcome_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_outcome_uk" ON "cle_v2"."case_outcome"
    ("case_id", "scope", COALESCE("article", ''), "outcome", "source_dataset");
CREATE INDEX IF NOT EXISTS "case_outcome_idx_filter" ON "cle_v2"."case_outcome"
    ("scope", "article", "outcome");
CREATE INDEX IF NOT EXISTS "case_outcome_idx_dataset" ON "cle_v2"."case_outcome" ("source_dataset");

CREATE TABLE IF NOT EXISTS "cle_v2"."case_status" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "status" text NOT NULL,                 -- pending | struck_out | referred_to_grand_chamber | final | overturned
    "status_date" date,
    "related_case_id" bigint,
    "raw_value" text,
    "source_dataset" text NOT NULL,
    "extractor_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "fk_case_status_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE,
    CONSTRAINT "fk_case_status_related" FOREIGN KEY ("related_case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_status_uk" ON "cle_v2"."case_status"
    ("case_id", "status", COALESCE("status_date", '-infinity'::date), "source_dataset");
CREATE INDEX IF NOT EXISTS "case_status_idx_related" ON "cle_v2"."case_status"
    ("related_case_id") WHERE "related_case_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_status_idx_status" ON "cle_v2"."case_status" ("status");
CREATE INDEX IF NOT EXISTS "case_status_idx_dataset" ON "cle_v2"."case_status" ("source_dataset");

-- ---------------------------------------------------------------------------
-- Corrected ECtHR edges for the rebuild (roadmap R6.1), built and reviewed
-- before anything is swapped. Empty until its gate has passed and the owner
-- has approved it. Natural keys only, so it can be built on db-dev and replayed.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "cle_v2"."echr_edge_v2_staging" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "source_ecli" text,
    "source_item_id" text,
    "target_ecli" text,
    "target_item_id" text,
    "scl_reference" text NOT NULL,          -- the HUDOC scl entry the edge comes from
    "appno" text,
    "rule" text NOT NULL,                   -- which disambiguation rule chose the target
    "build_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "echr_edge_v2_staging_source_check"
        CHECK ("source_ecli" IS NOT NULL OR "source_item_id" IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS "echr_edge_v2_staging_uk" ON "cle_v2"."echr_edge_v2_staging"
    (COALESCE("source_ecli", "source_item_id"), COALESCE("target_ecli", "target_item_id", ''),
     "scl_reference", "build_version");
CREATE INDEX IF NOT EXISTS "echr_edge_v2_staging_idx_source"
    ON "cle_v2"."echr_edge_v2_staging" ("build_version", COALESCE("source_ecli", "source_item_id"));
CREATE INDEX IF NOT EXISTS "echr_edge_v2_staging_idx_target"
    ON "cle_v2"."echr_edge_v2_staging" ("build_version", "target_ecli") WHERE "target_ecli" IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Correct citation counts, set-based (R1.4). Created here, called by nothing:
-- switching counts over is a separate change with a before/after report.
-- ---------------------------------------------------------------------------
-- For the given cases (all cases when NULL): cites_count = distinct cases
-- cited, cited_by_count = distinct citing cases, from resolved rows only,
-- leaving out self-loops, relation types marked not counted, and datasets not
-- registered as counted (fail closed: a dataset loaded before it is registered
-- is not counted). Relation types missing from the lookup count. Writes only
-- rows that change, and creates rows only for cases with a nonzero count.
--
-- SECURITY DEFINER: every table is schema-qualified and pg_temp is searched
-- last, so a caller cannot substitute a temporary table for one of them.

CREATE OR REPLACE FUNCTION "cle_v2"."refresh_case_citation_counts"(p_case_ids bigint[] DEFAULT NULL)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = "cle_v2", pg_temp
SET work_mem = '64MB'
AS $$
DECLARE
    changed integer;
BEGIN
    IF p_case_ids IS NULL THEN
        WITH counted AS MATERIALIZED (
            SELECT cc."source_case_id" AS s, cc."target_case_id" AS t
              FROM "cle_v2"."case_citation" cc
              LEFT JOIN "cle_v2"."citation_relation_type" rt ON rt."code" = cc."relation_type"
              JOIN "cle_v2"."citation_source_dataset" sd
                ON sd."code" = cc."source_dataset" AND sd."counted"
             WHERE cc."source_case_id" IS NOT NULL
               AND cc."target_case_id" IS NOT NULL
               AND cc."source_case_id" <> cc."target_case_id"
               AND COALESCE(rt."counted", true)
             GROUP BY 1, 2
        ),
        fresh AS (
            SELECT k.case_id, sum(k.cites)::int AS cites_count, sum(k.cited_by)::int AS cited_by_count
              FROM (
                    SELECT s AS case_id, 1 AS cites, 0 AS cited_by FROM counted
                    UNION ALL
                    SELECT t, 0, 1 FROM counted
                   ) k
             GROUP BY k.case_id
        ),
        target AS (
            SELECT COALESCE(f.case_id, x."case_id") AS case_id,
                   COALESCE(f.cites_count, 0) AS cites_count,
                   COALESCE(f.cited_by_count, 0) AS cited_by_count
              FROM fresh f
              FULL JOIN "cle_v2"."case_citation_counts" x ON x."case_id" = f.case_id
             WHERE x."case_id" IS NULL
                OR x."cites_count" IS DISTINCT FROM COALESCE(f.cites_count, 0)
                OR x."cited_by_count" IS DISTINCT FROM COALESCE(f.cited_by_count, 0)
        ),
        upserted AS (
            INSERT INTO "cle_v2"."case_citation_counts" AS cnt
                ("case_id", "cites_count", "cited_by_count", "updated_at")
            SELECT case_id, cites_count, cited_by_count, now() FROM target
            ON CONFLICT ("case_id") DO UPDATE
               SET "cites_count" = EXCLUDED."cites_count",
                   "cited_by_count" = EXCLUDED."cited_by_count",
                   "updated_at" = now()
            RETURNING 1
        )
        SELECT count(*) INTO changed FROM upserted;
    ELSE
        WITH scope AS (
            SELECT DISTINCT u.case_id
              FROM unnest(p_case_ids) AS u(case_id)
              JOIN "cle_v2"."cases" c ON c."id" = u.case_id
        ),
        counted AS NOT MATERIALIZED (
            SELECT cc."source_case_id" AS s, cc."target_case_id" AS t
              FROM "cle_v2"."case_citation" cc
              LEFT JOIN "cle_v2"."citation_relation_type" rt ON rt."code" = cc."relation_type"
              JOIN "cle_v2"."citation_source_dataset" sd
                ON sd."code" = cc."source_dataset" AND sd."counted"
             WHERE cc."source_case_id" IS NOT NULL
               AND cc."target_case_id" IS NOT NULL
               AND cc."source_case_id" <> cc."target_case_id"
               AND COALESCE(rt."counted", true)
        ),
        fresh AS (
            SELECT sc.case_id,
                   (SELECT count(DISTINCT k.t) FROM counted k WHERE k.s = sc.case_id)::int AS cites_count,
                   (SELECT count(DISTINCT k.s) FROM counted k WHERE k.t = sc.case_id)::int AS cited_by_count
              FROM scope sc
        ),
        target AS (
            SELECT f.case_id, f.cites_count, f.cited_by_count
              FROM fresh f
              LEFT JOIN "cle_v2"."case_citation_counts" x ON x."case_id" = f.case_id
             WHERE (x."case_id" IS NULL AND (f.cites_count > 0 OR f.cited_by_count > 0))
                OR (x."case_id" IS NOT NULL
                    AND (x."cites_count" IS DISTINCT FROM f.cites_count
                         OR x."cited_by_count" IS DISTINCT FROM f.cited_by_count))
        ),
        upserted AS (
            INSERT INTO "cle_v2"."case_citation_counts" AS cnt
                ("case_id", "cites_count", "cited_by_count", "updated_at")
            SELECT case_id, cites_count, cited_by_count, now() FROM target
            ON CONFLICT ("case_id") DO UPDATE
               SET "cites_count" = EXCLUDED."cites_count",
                   "cited_by_count" = EXCLUDED."cited_by_count",
                   "updated_at" = now()
            RETURNING 1
        )
        SELECT count(*) INTO changed FROM upserted;
    END IF;
    RETURN changed;
END;
$$;

REVOKE ALL ON FUNCTION "cle_v2"."refresh_case_citation_counts"(bigint[]) FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Last: everything that locks case_citation.
-- ---------------------------------------------------------------------------

-- How each link was found (R1.1).
ALTER TABLE "cle_v2"."case_citation"
    ADD COLUMN IF NOT EXISTS "match_method" text,
    ADD COLUMN IF NOT EXISTS "confidence" real,
    ADD COLUMN IF NOT EXISTS "target_ref_raw" text,
    ADD COLUMN IF NOT EXISTS "target_ref_scheme" text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_citation"'::regclass
           AND conname = 'case_citation_confidence_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_citation"
            ADD CONSTRAINT "case_citation_confidence_check"
            CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_citation"'::regclass
           AND conname = 'case_citation_target_ref_scheme_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_citation"
            ADD CONSTRAINT "case_citation_target_ref_scheme_check"
            CHECK ("target_ref_raw" IS NULL OR "target_ref_scheme" IS NOT NULL) NOT VALID;
    END IF;
END
$$;

COMMENT ON COLUMN "cle_v2"."case_citation"."match_method" IS
    'How the target was found: ecli | celex | case_number | appno | ljn | zaaknummer | metadata | formal_relation | name_date. NULL on rows loaded before 0009.';
COMMENT ON COLUMN "cle_v2"."case_citation"."confidence" IS
    'The extractor''s own estimate that the link is right, 0 to 1. NULL on rows loaded before 0009.';
COMMENT ON COLUMN "cle_v2"."case_citation"."target_ref_raw" IS
    'The cited reference, normalised, when it is not an ECLI or CELEX (a CJEU case number, an ECtHR application number, a Dutch case number). The text as written is in case_citation_mention.raw_text.';
COMMENT ON COLUMN "cle_v2"."case_citation"."target_ref_scheme" IS
    'Scheme of target_ref_raw: cjeu_case_number | echr_appno | nl_zaaknummer | ljn | name_date. Required when target_ref_raw is set.';

-- Every place a link occurs (R1.1, R1.3). case_citation keeps one row per
-- (source, target, relation, dataset); a judgment often cites the same case in
-- several paragraphs. Each occurrence is a row here, with where it is and,
-- later, how the court treats it (R5.4).
CREATE TABLE IF NOT EXISTS "cle_v2"."case_citation_mention" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "citation_id" bigint NOT NULL,
    "case_text_id" bigint,
    "text_field" text NOT NULL,             -- fulltext | summary | national_judgement_xml | metadata
    "language" text,
    "char_start" int,                       -- offsets into the text as stored when extracted
    "char_end" int,
    "raw_text" text NOT NULL,               -- the reference as written
    "context" text,                         -- up to ~300 characters around it
    "segment_id" bigint,
    "section" text,                         -- e.g. the ECtHR part quoting domestic law (decision D4)
    "treatment_label" text,                 -- follows | applies | distinguishes | departs_from (R5.4)
    "treatment_model" text,
    "treatment_confidence" real,
    "extractor_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "case_citation_mention_treatment_confidence_check"
        CHECK ("treatment_confidence" IS NULL OR "treatment_confidence" BETWEEN 0 AND 1),
    CONSTRAINT "case_citation_mention_offsets_check"
        CHECK ("char_start" IS NULL OR "char_end" IS NULL OR ("char_start" >= 0 AND "char_end" >= "char_start")),
    CONSTRAINT "fk_case_citation_mention_citation" FOREIGN KEY ("citation_id")
        REFERENCES "cle_v2"."case_citation" ("id") ON DELETE CASCADE,
    CONSTRAINT "fk_case_citation_mention_case_text" FOREIGN KEY ("case_text_id")
        REFERENCES "cle_v2"."case_text" ("id") ON DELETE SET NULL,
    CONSTRAINT "fk_case_citation_mention_segment" FOREIGN KEY ("segment_id")
        REFERENCES "cle_v2"."case_segment" ("id") ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_citation_mention_uk" ON "cle_v2"."case_citation_mention"
    ("citation_id", "text_field", COALESCE("language", ''), COALESCE("char_start", -1), md5("raw_text"));
CREATE INDEX IF NOT EXISTS "case_citation_mention_idx_segment"
    ON "cle_v2"."case_citation_mention" ("segment_id") WHERE "segment_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_citation_mention_idx_case_text"
    ON "cle_v2"."case_citation_mention" ("case_text_id") WHERE "case_text_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_citation_mention_idx_treatment"
    ON "cle_v2"."case_citation_mention" ("treatment_label") WHERE "treatment_label" IS NOT NULL;

-- For the ECtHR edge rebuild (R6.1): same columns and defaults as
-- case_citation, not its identity, indexes, foreign keys or triggers, so
-- archived rows keep their original id and nothing fires. Archive and restore
-- list their columns explicitly. Created after the ALTER above so it has the
-- new columns too.
CREATE TABLE IF NOT EXISTS "cle_v2"."case_citation_archive"
    (LIKE "cle_v2"."case_citation" INCLUDING DEFAULTS);
ALTER TABLE "cle_v2"."case_citation_archive"
    ADD COLUMN IF NOT EXISTS "archived_at" timestamptz DEFAULT now() NOT NULL,
    ADD COLUMN IF NOT EXISTS "archive_reason" text NOT NULL,
    ADD COLUMN IF NOT EXISTS "archive_batch" text NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_citation_archive"'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE "cle_v2"."case_citation_archive"
            ADD CONSTRAINT "case_citation_archive_pkey" PRIMARY KEY ("archive_batch", "id");
    END IF;
END
$$;

-- ---- 0010_case_citation_link_indexes.sql ----
-- Indexes on case_citation for the cross-dataset link columns of 0009.
--
-- A separate file from 0009 on purpose: the migrator applies each file in one
-- transaction, and here no ALTER TABLE precedes the index builds, so each build
-- takes only a SHARE lock on case_citation. API reads continue; writes to
-- case_citation wait for the scans. Apply outside the Monday ETL and Thursday
-- promotion windows.
--
--   case_citation_uk_unresolved_ref   idempotent unresolved rows referenced by
--                                     case number / application number, like
--                                     the existing _uk_unresolved_ecli/_celex
--   case_citation_idx_target_ref      late-binding resolution (roadmap R2.9)
--                                     looks rows up by reference
--   case_citation_idx_source_dataset  one-statement removal of a dataset, and
--                                     per-dataset verification counts
--
-- The two partial indexes cover no existing row (target_ref_raw is new and
-- NULL everywhere), but building them still reads the table once each. Measure
-- the build on db-dev first; the API container waits for the migrator.
--
-- The lookups of 0009 are not seeded from case_citation here: that would add
-- two more scans under this lock, and an empty db-dev would end up with
-- different rows than production. The count and API guard registers the
-- datasets present in production when it ships.

-- (migration only) SET LOCAL lock_timeout = '5s';
-- (migration only) SET LOCAL maintenance_work_mem = '128MB';

CREATE UNIQUE INDEX IF NOT EXISTS "case_citation_uk_unresolved_ref" ON "cle_v2"."case_citation"
    ("source_case_id", "target_ref_scheme", "target_ref_raw", COALESCE("relation_type", ''), "source_dataset")
    WHERE "target_case_id" IS NULL AND "target_ref_raw" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "case_citation_idx_target_ref" ON "cle_v2"."case_citation"
    ("target_ref_scheme", "target_ref_raw")
    WHERE "target_case_id" IS NULL AND "target_ref_raw" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "case_citation_idx_source_dataset" ON "cle_v2"."case_citation"
    ("source_dataset");

-- ---- 0011_legislation_external_keys.sql ----
-- EU, Council of Europe and UN acts in legislation (roadmap R3.1, R3.7).
--
-- Design: cjeu-migration docs/CROSS_DATASET_ROADMAP.md, Phase 3. Strictly
-- additive:
--
--   * jurisdiction gets the lookup rows the new acts point at (EU and CE are
--     already there in production, seeded by the migration's 10_lookups.sql;
--     UN is new). ON CONFLICT DO NOTHING, so existing rows are untouched.
--   * legislation, legal_provision and case_law_reference gain nullable
--     columns (no default, so no row is rewritten): where a row came from
--     (source_dataset, extractor_version; case_law_reference already has
--     source_dataset), and on legislation the ELI and the year a CELEX number
--     gives (enacted_year; enacted_date stays for real dates).
--   * Partial unique indexes that cover only the new rows, so existing rows
--     cannot violate them:
--       legislation_uk_external      (scheme, identifier) for the new schemes
--                                    'celex', 'coe_treaty', 'un_treaty'. The
--                                    265k BWB rows (scheme 'bwb') are outside
--                                    the predicate; legislation has no unique
--                                    key on (scheme, identifier) for them.
--       legal_provision_uk_external  one provision per act, element type,
--                                    article and paragraph, for rows with a
--                                    source_dataset (all existing rows have
--                                    none).
--     Loaders restate these predicates in ON CONFLICT, which also works
--     against the plain indexes of case-law-explorer db/schema.sql.
--
-- Sizes and locks: legislation holds about 265k rows and legal_provision at
-- most ~887k (legacy rs_law_element had 887,208 rows, split between the two).
-- ALTER TABLE ... ADD COLUMN without a default only changes the catalog, but
-- takes ACCESS EXCLUSIVE on legislation and legal_provision until the end of
-- this file (the migrator runs each file in one transaction). The index
-- builds read each table once while that lock is held; at these sizes that is
-- about a second, during which API reads of legislation / legal_provision
-- wait. Last, case_law_reference (about 8.2M rows) gains a nullable
-- extractor_version column for the new law-reference datasets: catalog only,
-- no scan, so its ACCESS EXCLUSIVE lock is held for the few milliseconds from
-- that statement to the end of the file (taken last for that reason, as 0009
-- does with case_citation). Its index for R3.5 is in
-- 0014_case_law_reference_indexes.sql.
--
-- Before applying: SELECT scheme, count(*), count(DISTINCT identifier) FROM
-- legislation GROUP BY scheme; must show no rows for the new schemes (the
-- unique index would fail on duplicates there; none are expected, the
-- migration loaded only 'bwb').

-- (migration only) SET LOCAL lock_timeout = '5s';

INSERT INTO "cle_v2"."jurisdiction" ("iso_code", "name", "type") VALUES
    ('EU', 'European Union', 'supranational'),
    ('CE', 'Council of Europe', 'international'),
    ('UN', 'United Nations', 'international'),
    ('INTL', 'International', 'international')
ON CONFLICT ("iso_code") DO NOTHING;

ALTER TABLE "cle_v2"."legislation"
    ADD COLUMN IF NOT EXISTS "source_dataset" text,     -- curated_external | cellar_celex | ...; NULL for BWB/LIDO rows
    ADD COLUMN IF NOT EXISTS "extractor_version" text,
    ADD COLUMN IF NOT EXISTS "eli" text,                -- European Legislation Identifier, where known
    ADD COLUMN IF NOT EXISTS "enacted_year" smallint;   -- year from the identifier (CELEX), when no date is known

ALTER TABLE "cle_v2"."legal_provision"
    ADD COLUMN IF NOT EXISTS "source_dataset" text,     -- echr_article | ...; NULL for BWB/LIDO rows
    ADD COLUMN IF NOT EXISTS "extractor_version" text;

CREATE UNIQUE INDEX IF NOT EXISTS "legislation_uk_external"
    ON "cle_v2"."legislation" ("scheme", "identifier")
    WHERE "scheme" IN ('celex', 'coe_treaty', 'un_treaty');

CREATE UNIQUE INDEX IF NOT EXISTS "legislation_uk_intl_treaty"
    ON "cle_v2"."legislation" ("scheme", "identifier")
    WHERE "scheme" = 'intl_treaty';

CREATE INDEX IF NOT EXISTS "legislation_idx_source_dataset"
    ON "cle_v2"."legislation" ("source_dataset")
    WHERE "source_dataset" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "legal_provision_uk_external"
    ON "cle_v2"."legal_provision"
    ("legislation_id", "element_type", "article_label", COALESCE("paragraph", ''))
    WHERE "source_dataset" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "legal_provision_idx_source_dataset"
    ON "cle_v2"."legal_provision" ("source_dataset")
    WHERE "source_dataset" IS NOT NULL;

-- Last: the only statement that locks case_law_reference.
ALTER TABLE "cle_v2"."case_law_reference"
    ADD COLUMN IF NOT EXISTS "extractor_version" text;   -- set by the new law-reference loaders (echr_article, ...)

-- ---- 0012_case_law_reference_provenance.sql ----
-- Provenance columns on case_law_reference for the law-reference extractors
-- (cjeu-migration docs/CROSS_DATASET_ROADMAP.md, R3.2-R3.4).
--
-- extractor_version may already exist (0011 adds it for the ECHR article
-- references); ADD COLUMN IF NOT EXISTS keeps this file safe either way.
--
-- Ground rule 5 of the roadmap: every link carries its extractor version,
-- match method and confidence. case_citation got them in 0009; this does the
-- same for case_law_reference, which new data now reaches from three new
-- source datasets (cellar_law_ref, rs_text_eu_law, echr_text_eu_law).
--
-- Strictly additive:
--   * three nullable columns, no default: existing rows are not rewritten
--     (metadata-only change; ACCESS EXCLUSIVE on case_law_reference for
--     milliseconds, which is why nothing else in this file touches the table);
--   * one CHECK, NOT VALID: no scan of existing rows (all NULL in the new
--     column anyway); enforced for new and updated rows.
--
-- The unique index the new datasets need is in 0014: built here, it would scan
-- case_law_reference while this file holds ACCESS EXCLUSIVE on it.

-- (migration only) SET LOCAL lock_timeout = '5s';

ALTER TABLE "cle_v2"."case_law_reference"
    ADD COLUMN IF NOT EXISTS "extractor_version" text,
    ADD COLUMN IF NOT EXISTS "match_method"      text,
    ADD COLUMN IF NOT EXISTS "confidence"        real;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_law_reference"'::regclass
           AND conname = 'case_law_reference_confidence_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_law_reference"
            ADD CONSTRAINT "case_law_reference_confidence_check"
            CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1) NOT VALID;
    END IF;
END
$$;

COMMENT ON COLUMN "cle_v2"."case_law_reference"."extractor_version" IS
    'Extractor that wrote the row, e.g. eu_law_text/1.0.0. NULL on rows loaded before 0012.';
COMMENT ON COLUMN "cle_v2"."case_law_reference"."match_method" IS
    'How the act was identified: celex_metadata | act_number | treaty_article | act_name. NULL on rows loaded before 0012.';
COMMENT ON COLUMN "cle_v2"."case_law_reference"."confidence" IS
    'The extractor''s own estimate that the reference is right, 0 to 1. NULL on rows loaded before 0012.';

-- ---- 0013_case_timeline_view.sql ----
-- Case context: confidence on outcomes and status, and the procedural links a
-- case timeline is built from (roadmap R5.1-R5.3, cjeu-migration
-- docs/CROSS_DATASET_ROADMAP.md, Phase 5).
--
-- Strictly additive:
--
--   * case_outcome and case_status (empty tables from 0009) gain a nullable
--     "confidence" column (no default, nothing rewritten) with a NOT VALID
--     check, like case_citation.confidence. The ACCESS EXCLUSIVE lock is on
--     these two small tables only, which nothing reads yet.
--   * case_procedural_link is a new view over case_citation: no table is
--     changed, scanned or locked beyond ACCESS SHARE while the view is
--     created.
--
-- Depends on 0009 (case_outcome, case_status, citation_relation_type).
--
-- case_procedural_link: one row per resolved procedural relation, oriented
-- in time (earlier_case_id happened before later_case_id), from the relation
-- types whose direction is known:
--
--   relation_type          stored as                      step
--   preliminary_reference  national referral -> ruling    referral
--   opinion_of             AG opinion -> judgment         opinion
--   subject_to_appeal      decision -> its appeal         appeal      (Cellar)
--   reexamined_by          decision -> its review         review      (Cellar)
--   national_follow_up     national decision -> ruling    follow_up   (reversed)
--   appeal_of              appeal -> decision appealed    appeal      (reversed)
--   earlier_instance       decision -> earlier decision   earlier_instance (reversed)
--
-- and the Rechtspraak formal relations (source_dataset rs_formal_relation*),
-- whose stored direction is not reliable, oriented by decision date (rows
-- with equal or missing dates are left out, order_basis 'date'):
--
--   hogerberoep -> appeal, cassatie -> cassation, conclusie -> opinion,
--   prejudicielevraag -> referral, tussenuitspraak -> interim
--
-- Left out: citations, identity relations (replaced_by), joins, Cellar's
-- referred_for_preliminary_ruling (it files referrals and follow-ups alike;
-- the Phase 2 extractors re-type it), unresolved rows and self-loops. The
-- same pair can appear under several datasets or both stored directions; the
-- timeline query (case-law-explorer db/queries/case_timeline.sql) groups them.
--
-- Each branch exposes plain columns of case_citation as earlier/later ids, so
-- a filter on either id uses case_citation_idx_source / _idx_target.

-- (migration only) SET LOCAL lock_timeout = '5s';

ALTER TABLE "cle_v2"."case_outcome" ADD COLUMN IF NOT EXISTS "confidence" real;
ALTER TABLE "cle_v2"."case_status" ADD COLUMN IF NOT EXISTS "confidence" real;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_outcome"'::regclass
           AND conname = 'case_outcome_confidence_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_outcome"
            ADD CONSTRAINT "case_outcome_confidence_check"
            CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_status"'::regclass
           AND conname = 'case_status_confidence_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_status"
            ADD CONSTRAINT "case_status_confidence_check"
            CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1) NOT VALID;
    END IF;
END
$$;

COMMENT ON COLUMN "cle_v2"."case_outcome"."confidence" IS
    'How sure the extractor is of this outcome (0-1). NULL on rows loaded before 0013.';
COMMENT ON COLUMN "cle_v2"."case_status"."confidence" IS
    'How sure the extractor is of this status (0-1). NULL on rows loaded before 0013.';

CREATE OR REPLACE VIEW "cle_v2"."case_procedural_link" AS
SELECT cc."id" AS "citation_id",
       cc."source_case_id" AS "earlier_case_id",
       cc."target_case_id" AS "later_case_id",
       CASE cc."relation_type"
           WHEN 'preliminary_reference' THEN 'referral'
           WHEN 'opinion_of' THEN 'opinion'
           WHEN 'subject_to_appeal' THEN 'appeal'
           WHEN 'reexamined_by' THEN 'review'
       END AS "step",
       cc."relation_type",
       cc."source_dataset",
       'relation'::text AS "order_basis",
       cc."match_method",
       cc."confidence"
  FROM "cle_v2"."case_citation" cc
 WHERE cc."relation_type" IN ('preliminary_reference', 'opinion_of', 'subject_to_appeal', 'reexamined_by')
   AND cc."target_case_id" IS NOT NULL
   AND cc."source_case_id" <> cc."target_case_id"
UNION ALL
SELECT cc."id",
       cc."target_case_id",
       cc."source_case_id",
       CASE cc."relation_type"
           WHEN 'national_follow_up' THEN 'follow_up'
           WHEN 'appeal_of' THEN 'appeal'
           WHEN 'earlier_instance' THEN 'earlier_instance'
       END,
       cc."relation_type",
       cc."source_dataset",
       'relation'::text,
       cc."match_method",
       cc."confidence"
  FROM "cle_v2"."case_citation" cc
 WHERE cc."relation_type" IN ('national_follow_up', 'appeal_of', 'earlier_instance')
   AND cc."target_case_id" IS NOT NULL
   AND cc."source_case_id" <> cc."target_case_id"
UNION ALL
SELECT cc."id",
       cc."source_case_id",
       cc."target_case_id",
       CASE cc."relation_type"
           WHEN 'hogerberoep' THEN 'appeal'
           WHEN 'cassatie' THEN 'cassation'
           WHEN 'conclusie' THEN 'opinion'
           WHEN 'prejudicielevraag' THEN 'referral'
           WHEN 'tussenuitspraak' THEN 'interim'
       END,
       cc."relation_type",
       cc."source_dataset",
       'date'::text,
       cc."match_method",
       cc."confidence"
  FROM "cle_v2"."case_citation" cc
  JOIN "cle_v2"."cases" s ON s."id" = cc."source_case_id"
  JOIN "cle_v2"."cases" t ON t."id" = cc."target_case_id"
 WHERE cc."relation_type" IN ('hogerberoep', 'cassatie', 'conclusie', 'prejudicielevraag', 'tussenuitspraak')
   AND starts_with(cc."source_dataset", 'rs_formal_relation')
   AND s."date_decision" < t."date_decision"
UNION ALL
SELECT cc."id",
       cc."target_case_id",
       cc."source_case_id",
       CASE cc."relation_type"
           WHEN 'hogerberoep' THEN 'appeal'
           WHEN 'cassatie' THEN 'cassation'
           WHEN 'conclusie' THEN 'opinion'
           WHEN 'prejudicielevraag' THEN 'referral'
           WHEN 'tussenuitspraak' THEN 'interim'
       END,
       cc."relation_type",
       cc."source_dataset",
       'date'::text,
       cc."match_method",
       cc."confidence"
  FROM "cle_v2"."case_citation" cc
  JOIN "cle_v2"."cases" s ON s."id" = cc."source_case_id"
  JOIN "cle_v2"."cases" t ON t."id" = cc."target_case_id"
 WHERE cc."relation_type" IN ('hogerberoep', 'cassatie', 'conclusie', 'prejudicielevraag', 'tussenuitspraak')
   AND starts_with(cc."source_dataset", 'rs_formal_relation')
   AND s."date_decision" > t."date_decision";

COMMENT ON VIEW "cle_v2"."case_procedural_link" IS
    'Resolved procedural relations oriented in time (earlier_case_id before later_case_id), for case timelines (roadmap R5.3). See 0013_case_timeline_view.sql.';

-- ---- 0014_case_law_reference_indexes.sql ----
-- Unique keys for case_law_reference rows that are resolved AND keep their raw
-- reference. None of 0001's three keys covers that shape: _uk_provision and
-- _uk_legislation require raw_resource IS NULL, _uk_raw requires both ids NULL.
-- Two partial indexes over disjoint datasets, so their predicates never overlap:
--
--   case_law_reference_uk_bwb_resolved   rs_lido_sqlite rows the RS loader now
--                                        resolves to their act (R3.5)
--   case_law_reference_uk_resolved_ref   Cellar and the new EU-law text datasets
--                                        resolved to an act or provision (R3.2–R3.4)
--
-- In one file, separate from 0011/0012, so the two builds take only a SHARE
-- lock on case_law_reference (about 8.2M rows; one scan each): reads continue,
-- writes wait. Measure on db-dev and apply outside the Monday ETL and Thursday
-- promotion windows. Before applying, both counts below must be 0:
--
--   SELECT count(*) FROM case_law_reference
--    WHERE source_dataset = 'rs_lido_sqlite' AND legislation_id IS NOT NULL;
--   SELECT count(*) FROM case_law_reference
--    WHERE raw_resource IS NOT NULL AND (legislation_id IS NOT NULL OR provision_id IS NOT NULL)
--      AND source_dataset IN ('cellar_sparql', 'cellar_law_ref', 'rs_text_eu_law', 'echr_text_eu_law');

-- (migration only) SET LOCAL lock_timeout = '5s';
-- (migration only) SET LOCAL maintenance_work_mem = '128MB';

CREATE UNIQUE INDEX IF NOT EXISTS "case_law_reference_uk_bwb_resolved"
    ON "cle_v2"."case_law_reference"
    ("case_id", "raw_scheme", "raw_resource", COALESCE("raw_subdivision", ''), "role", "source_dataset")
    WHERE "source_dataset" = 'rs_lido_sqlite'
      AND "provision_id" IS NULL
      AND "legislation_id" IS NOT NULL
      AND "raw_resource" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "case_law_reference_uk_resolved_ref"
    ON "cle_v2"."case_law_reference"
    ("case_id", "raw_scheme", "raw_resource", COALESCE("raw_subdivision", ''), "role", "source_dataset")
    WHERE "raw_resource" IS NOT NULL
      AND ("legislation_id" IS NOT NULL OR "provision_id" IS NOT NULL)
      AND "source_dataset" IN ('cellar_sparql', 'cellar_law_ref', 'rs_text_eu_law', 'echr_text_eu_law');

-- ---- 0017_legislation_fulltext_and_judges.sql ----
ALTER TABLE "cle_v2"."legislation"
    ADD COLUMN IF NOT EXISTS "short_title"           text,
    ADD COLUMN IF NOT EXISTS "in_force"              boolean,
    ADD COLUMN IF NOT EXISTS "date_document"         date,
    ADD COLUMN IF NOT EXISTS "date_entry_into_force" date,
    ADD COLUMN IF NOT EXISTS "eli"                   text,
    ADD COLUMN IF NOT EXISTS "subjects"              text[],
    ADD COLUMN IF NOT EXISTS "legal_basis"           text[],
    ADD COLUMN IF NOT EXISTS "amending_acts"         text[],
    ADD COLUMN IF NOT EXISTS "metadata_source"       text,
    ADD COLUMN IF NOT EXISTS "metadata_fetched_at"   timestamptz,
    ADD COLUMN IF NOT EXISTS "fulltext_fetched_at"   timestamptz;

CREATE INDEX IF NOT EXISTS "legislation_idx_fulltext_pending"
    ON "cle_v2"."legislation" ("scheme", "id")
    WHERE "fulltext_fetched_at" IS NULL;

ALTER TABLE "cle_v2"."case_judge"
    ADD COLUMN IF NOT EXISTS "source_dataset"    text,
    ADD COLUMN IF NOT EXISTS "extractor_version" text,
    ADD COLUMN IF NOT EXISTS "confidence"        real;

CREATE INDEX IF NOT EXISTS "case_judge_idx_source_dataset"
    ON "cle_v2"."case_judge" ("source_dataset")
    WHERE "source_dataset" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "judge_idx_full_name_lower"
    ON "cle_v2"."judge" (lower("full_name"))
    WHERE "full_name" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "cjeu_ag_opinion_idx_ag_lower"
    ON "cle_v2"."cjeu_ag_opinion" (lower("advocate_general"))
    WHERE "advocate_general" IS NOT NULL;

-- Mirror of caselaw-coolify 0018_legislation_citing_counts.sql
CREATE INDEX IF NOT EXISTS "case_law_reference_idx_legislation_case"
    ON "cle_v2"."case_law_reference" ("legislation_id", "case_id")
    WHERE "legislation_id" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "case_law_reference_uk_cjeu_treaty"
    ON "cle_v2"."case_law_reference"
    ("case_id", "raw_scheme", "raw_resource", COALESCE("raw_subdivision", ''), "role", "source_dataset")
    WHERE "raw_resource" IS NOT NULL
      AND ("legislation_id" IS NOT NULL OR "provision_id" IS NOT NULL)
      AND "source_dataset" = 'cjeu_text_treaty';

CREATE MATERIALIZED VIEW IF NOT EXISTS "cle_v2"."legislation_citing_counts" AS
WITH resolved AS (
    SELECT DISTINCT
        COALESCE(r."legislation_id", lp."legislation_id") AS "legislation_id",
        r."case_id",
        CASE
            WHEN c."ecli" LIKE 'ECLI:EU:%'      THEN 'CJEU'
            WHEN c."ecli" LIKE 'ECLI:NL:%'      THEN 'RS'
            WHEN c."ecli" LIKE 'ECLI:CE:ECHR:%' THEN 'ECHR'
            ELSE NULL
        END AS "corpus"
    FROM "cle_v2"."case_law_reference" r
    LEFT JOIN "cle_v2"."legal_provision" lp
           ON r."legislation_id" IS NULL
          AND lp."id" = r."provision_id"
    JOIN "cle_v2"."cases" c
      ON c."id" = r."case_id"
    WHERE (r."legislation_id" IS NOT NULL OR r."provision_id" IS NOT NULL)
      AND COALESCE(r."legislation_id", lp."legislation_id") IS NOT NULL
)
SELECT
    "legislation_id",
    COUNT(*)::int                                    AS "total_count",
    COUNT(*) FILTER (WHERE "corpus" = 'CJEU')::int   AS "cjeu_count",
    COUNT(*) FILTER (WHERE "corpus" = 'RS')::int     AS "rs_count",
    COUNT(*) FILTER (WHERE "corpus" = 'ECHR')::int   AS "echr_count"
FROM resolved
GROUP BY "legislation_id";

CREATE UNIQUE INDEX IF NOT EXISTS "legislation_citing_counts_legislation_id"
    ON "cle_v2"."legislation_citing_counts" ("legislation_id");

CREATE INDEX IF NOT EXISTS "legislation_citing_counts_total_desc"
    ON "cle_v2"."legislation_citing_counts" ("total_count" DESC, "legislation_id");

-- Mirror of caselaw-coolify 0019_legislation_equivalence.sql
CREATE TABLE IF NOT EXISTS "cle_v2"."legislation_equivalence" (
    "canonical_legislation_id" bigint      NOT NULL REFERENCES "cle_v2"."legislation"("id") ON DELETE CASCADE,
    "alias_legislation_id"     bigint      NOT NULL REFERENCES "cle_v2"."legislation"("id") ON DELETE CASCADE,
    "relation"                 text        NOT NULL DEFAULT 'same_instrument'
                               CHECK ("relation" IN ('same_instrument', 'consolidates')),
    "source"                   text        NOT NULL DEFAULT 'curated',
    "created_at"               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("canonical_legislation_id", "alias_legislation_id"),
    UNIQUE ("alias_legislation_id"),
    CHECK ("canonical_legislation_id" <> "alias_legislation_id")
);

CREATE INDEX IF NOT EXISTS "legislation_equivalence_idx_canonical"
    ON "cle_v2"."legislation_equivalence" ("canonical_legislation_id");

-- Mirror of caselaw-coolify 0020_echr_text_extractors.sql
CREATE UNIQUE INDEX IF NOT EXISTS "case_law_reference_uk_echr_treaty"
    ON "cle_v2"."case_law_reference"
    ("case_id", "raw_scheme", "raw_resource", COALESCE("raw_subdivision", ''), "role", "source_dataset")
    WHERE "raw_resource" IS NOT NULL
      AND ("legislation_id" IS NOT NULL OR "provision_id" IS NOT NULL)
      AND "source_dataset" = 'echr_text_treaty';

INSERT INTO "cle_v2"."citation_source_dataset" (code, description, corpus, counted, active_in_api)
VALUES ('echr_text_echr', 'ECtHR full-text precedent extraction for empty-scl judgments.', 'ECHR', true, true)
ON CONFLICT (code) DO NOTHING;

-- Mirror of caselaw-coolify 0022_person_governance_overrides.sql
CREATE TABLE IF NOT EXISTS "cle_v2"."person_governance_override" (
    "id"               bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    "match_name"       text        NOT NULL,
    "match_role"       text        CHECK ("match_role" IS NULL OR "match_role" IN ('judge', 'rapporteur', 'advocate_general')),
    "match_court"      text        CHECK ("match_court" IS NULL OR "match_court" IN ('CJEU', 'ECHR', 'RS')),
    "action"           text        NOT NULL CHECK ("action" IN ('suppress', 'rename', 'split_exclude')),
    "replacement_name" text,
    "reason"           text        NOT NULL,
    "ticket_ref"       text,
    "active"           boolean     NOT NULL DEFAULT true,
    "created_at"       timestamptz NOT NULL DEFAULT now(),
    "updated_at"       timestamptz NOT NULL DEFAULT now(),
    CHECK ("action" <> 'rename' OR ("replacement_name" IS NOT NULL AND length(trim("replacement_name")) > 0))
);

CREATE UNIQUE INDEX IF NOT EXISTS "person_governance_override_uk_active"
    ON "cle_v2"."person_governance_override" (
        lower("match_name"),
        COALESCE("match_role", ''),
        COALESCE("match_court", ''),
        "action"
    )
    WHERE "active" = true;

CREATE INDEX IF NOT EXISTS "person_governance_override_idx_updated_at"
    ON "cle_v2"."person_governance_override" ("updated_at" DESC);
