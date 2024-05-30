/*
 * Copyright 2019-2022 The OpenSSL Project Authors. All Rights Reserved.
 *
 * Licensed under the Apache License 2.0 (the "License").  You may not use
 * this file except in compliance with the License.  You can obtain a copy
 * in the file LICENSE in the source distribution or at
 * https://www.openssl.org/source/license.html
 */

#ifndef OPENSSL_CORE_NAMES_H
# define OPENSSL_CORE_NAMES_H
# pragma once

# ifdef __cplusplus
extern "C" {
# endif

/* Well known parameter names that core passes to providers */
#define OSSL_PROV_PARAM_CORE_VERSION         "openssl-version" /* utf8_ptr */
#define OSSL_PROV_PARAM_CORE_PROV_NAME       "provider-name"   /* utf8_ptr */
#define OSSL_PROV_PARAM_CORE_MODULE_FILENAME "module-filename" /* utf8_ptr */

/* Well known parameter names that Providers can define */
#define OSSL_PROV_PARAM_NAME            "name"                /* utf8_ptr */
#define OSSL_PROV_PARAM_VERSION         "version"             /* utf8_ptr */
#define OSSL_PROV_PARAM_BUILDINFO       "buildinfo"           /* utf8_ptr */
#define OSSL_PROV_PARAM_STATUS          "status"              /* uint */
#define OSSL_PROV_PARAM_SECURITY_CHECKS "security-checks"     /* uint */

/* Self test callback parameters */
#define OSSL_PROV_PARAM_SELF_TEST_PHASE  "st-phase" /* utf8_string */
#define OSSL_PROV_PARAM_SELF_TEST_TYPE   "st-type"  /* utf8_string */
#define OSSL_PROV_PARAM_SELF_TEST_DESC   "st-desc"  /* utf8_string */

/*-
 * Provider-native object abstractions
 *
 * These are used when a provider wants to pass object data or an object
 * reference back to libcrypto.  This is only useful for provider functions
 * that take a callback to which an OSSL_PARAM array with these parameters
 * can be passed.
 *
 * This set of parameter names is explained in detail in provider-object(7)
 * (doc/man7/provider-object.pod)
 */
#define OSSL_OBJECT_PARAM_TYPE              "type"      /* INTEGER */
#define OSSL_OBJECT_PARAM_DATA_TYPE         "data-type" /* UTF8_STRING */
#define OSSL_OBJECT_PARAM_DATA_STRUCTURE    "data-structure" /* UTF8_STRING */
#define OSSL_OBJECT_PARAM_REFERENCE         "reference" /* OCTET_STRING */
#define OSSL_OBJECT_PARAM_DATA              "data" /* OCTET_STRING or UTF8_STRING */
#define OSSL_OBJECT_PARAM_DESC              "desc"      /* UTF8_STRING */

/*
 * Algorithm parameters
 * If "engine" or "properties" are specified, they should always be paired
 * with the algorithm type.
 * Note these are common names that are shared by many types (such as kdf, mac,
 * and pkey) e.g: see OSSL_MAC_PARAM_DIGEST below.
 */
#define OSSL_ALG_PARAM_DIGEST       "digest"    /* utf8_string */
#define OSSL_ALG_PARAM_CIPHER       "cipher"    /* utf8_string */
#define OSSL_ALG_PARAM_ENGINE       "engine"    /* utf8_string */
#define OSSL_ALG_PARAM_MAC          "mac"       /* utf8_string */
#define OSSL_ALG_PARAM_PROPERTIES   "properties"/* utf8_string */

/* cipher parameters */
#define OSSL_CIPHER_PARAM_PADDING              "padding"      /* uint */
#define OSSL_CIPHER_PARAM_USE_BITS             "use-bits"     /* uint */
#define OSSL_CIPHER_PARAM_TLS_VERSION          "tls-version"  /* uint */
#define OSSL_CIPHER_PARAM_TLS_MAC              "tls-mac"      /* octet_ptr */
#define OSSL_CIPHER_PARAM_TLS_MAC_SIZE         "tls-mac-size" /* size_t */
#define OSSL_CIPHER_PARAM_MODE                 "mode"         /* uint */
#define OSSL_CIPHER_PARAM_BLOCK_SIZE           "blocksize"    /* size_t */
#define OSSL_CIPHER_PARAM_AEAD                 "aead"         /* int, 0 or 1 */
#define OSSL_CIPHER_PARAM_CUSTOM_IV            "custom-iv"    /* int, 0 or 1 */
#define OSSL_CIPHER_PARAM_CTS                  "cts"          /* int, 0 or 1 */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK      "tls-multi"    /* int, 0 or 1 */
#define OSSL_CIPHER_PARAM_HAS_RAND_KEY         "has-randkey"  /* int, 0 or 1 */
#define OSSL_CIPHER_PARAM_KEYLEN               "keylen"       /* size_t */
#define OSSL_CIPHER_PARAM_IVLEN                "ivlen"        /* size_t */
#define OSSL_CIPHER_PARAM_IV                   "iv"           /* octet_string OR octet_ptr */
#define OSSL_CIPHER_PARAM_UPDATED_IV           "updated-iv"   /* octet_string OR octet_ptr */
#define OSSL_CIPHER_PARAM_NUM                  "num"          /* uint */
#define OSSL_CIPHER_PARAM_ROUNDS               "rounds"       /* uint */
#define OSSL_CIPHER_PARAM_AEAD_TAG             "tag"          /* octet_string */
#define OSSL_CIPHER_PARAM_AEAD_TLS1_AAD        "tlsaad"       /* octet_string */
#define OSSL_CIPHER_PARAM_AEAD_TLS1_AAD_PAD    "tlsaadpad"    /* size_t */
#define OSSL_CIPHER_PARAM_AEAD_TLS1_IV_FIXED   "tlsivfixed"   /* octet_string */
#define OSSL_CIPHER_PARAM_AEAD_TLS1_GET_IV_GEN "tlsivgen"     /* octet_string */
#define OSSL_CIPHER_PARAM_AEAD_TLS1_SET_IV_INV "tlsivinv"     /* octet_string */
#define OSSL_CIPHER_PARAM_AEAD_IVLEN           OSSL_CIPHER_PARAM_IVLEN
#define OSSL_CIPHER_PARAM_AEAD_TAGLEN          "taglen"       /* size_t */
#define OSSL_CIPHER_PARAM_AEAD_MAC_KEY         "mackey"       /* octet_string */
#define OSSL_CIPHER_PARAM_RANDOM_KEY           "randkey"      /* octet_string */
#define OSSL_CIPHER_PARAM_RC2_KEYBITS          "keybits"      /* size_t */
#define OSSL_CIPHER_PARAM_SPEED                "speed"        /* uint */
#define OSSL_CIPHER_PARAM_CTS_MODE             "cts_mode"     /* utf8_string */
/* For passing the AlgorithmIdentifier parameter in DER form */
#define OSSL_CIPHER_PARAM_ALGORITHM_ID_PARAMS  "alg_id_param" /* octet_string */

#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_MAX_SEND_FRAGMENT                    \
    "tls1multi_maxsndfrag" /* uint */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_MAX_BUFSIZE                          \
    "tls1multi_maxbufsz"   /* size_t */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_INTERLEAVE                           \
    "tls1multi_interleave" /* uint */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_AAD                                  \
    "tls1multi_aad"        /* octet_string */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_AAD_PACKLEN                          \
    "tls1multi_aadpacklen" /* uint */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_ENC                                  \
    "tls1multi_enc"        /* octet_string */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_ENC_IN                               \
    "tls1multi_encin"      /* octet_string */
#define OSSL_CIPHER_PARAM_TLS1_MULTIBLOCK_ENC_LEN                              \
    "tls1multi_enclen"     /* size_t */

/* OSSL_CIPHER_PARAM_CTS_MODE Values */
#define OSSL_CIPHER_CTS_MODE_CS1 "CS1"
#define OSSL_CIPHER_CTS_MODE_CS2 "CS2"
#define OSSL_CIPHER_CTS_MODE_CS3 "CS3"

/* digest parameters */
#define OSSL_DIGEST_PARAM_XOFLEN       "xoflen"        /* size_t */
#define OSSL_DIGEST_PARAM_SSL3_MS      "ssl3-ms"       /* octet string */
#define OSSL_DIGEST_PARAM_PAD_TYPE     "pad-type"      /* uint */
#define OSSL_DIGEST_PARAM_MICALG       "micalg"        /* utf8 string */
#define OSSL_DIGEST_PARAM_BLOCK_SIZE   "blocksize"     /* size_t */
#define OSSL_DIGEST_PARAM_SIZE         "size"          /* size_t */
#define OSSL_DIGEST_PARAM_XOF          "xof"           /* int, 0 or 1 */
#define OSSL_DIGEST_PARAM_ALGID_ABSENT "algid-absent"  /* int, 0 or 1 */

/* Known DIGEST names (not a complete list) */
#define OSSL_DIGEST_NAME_MD5            "MD5"
#define OSSL_DIGEST_NAME_MD5_SHA1       "MD5-SHA1"
#define OSSL_DIGEST_NAME_SHA1           "SHA1"
#define OSSL_DIGEST_NAME_SHA2_224       "SHA2-224"
#define OSSL_DIGEST_NAME_SHA2_256       "SHA2-256"
#define OSSL_DIGEST_NAME_SHA2_384       "SHA2-384"
#define OSSL_DIGEST_NAME_SHA2_512       "SHA2-512"
#define OSSL_DIGEST_NAME_SHA2_512_224   "SHA2-512/224"
#define OSSL_DIGEST_NAME_SHA2_512_256   "SHA2-512/256"
#define OSSL_DIGEST_NAME_MD2            "MD2"
#define OSSL_DIGEST_NAME_MD4            "MD4"
#define OSSL_DIGEST_NAME_MDC2           "MDC2"
#define OSSL_DIGEST_NAME_RIPEMD160      "RIPEMD160"
#define OSSL_DIGEST_NAME_SHA3_224       "SHA3-224"
#define OSSL_DIGEST_NAME_SHA3_256       "SHA3-256"
#define OSSL_DIGEST_NAME_SHA3_384       "SHA3-384"
#define OSSL_DIGEST_NAME_SHA3_512       "SHA3-512"
#define OSSL_DIGEST_NAME_KECCAK_KMAC128 "KECCAK-KMAC-128"
#define OSSL_DIGEST_NAME_KECCAK_KMAC256 "KECCAK-KMAC-256"
#define OSSL_DIGEST_NAME_SM3            "SM3"

/* MAC parameters */
#define OSSL_MAC_PARAM_KEY            "key"            /* octet string */
#define OSSL_MAC_PARAM_IV             "iv"             /* octet string */
#define OSSL_MAC_PARAM_CUSTOM         "custom"         /* utf8 string */
#define OSSL_MAC_PARAM_SALT           "salt"           /* octet string */
#define OSSL_MAC_PARAM_XOF            "xof"            /* int, 0 or 1 */
#define OSSL_MAC_PARAM_DIGEST_NOINIT  "digest-noinit"  /* int, 0 or 1 */
#define OSSL_MAC_PARAM_DIGEST_ONESHOT "digest-oneshot" /* int, 0 or 1 */
#define OSSL_MAC_PARAM_C_ROUNDS       "c-rounds"       /* unsigned int */
#define OSSL_MAC_PARAM_D_ROUNDS       "d-rounds"       /* unsigned int */

/*
 * If "engine" or "properties" are specified, they should always be paired
 * with "cipher" or "digest".
 */
#define OSSL_MAC_PARAM_CIPHER           OSSL_ALG_PARAM_CIPHER     /* utf8 string */
#define OSSL_MAC_PARAM_DIGEST           OSSL_ALG_PARAM_DIGEST     /* utf8 string */
#define OSSL_MAC_PARAM_PROPERTIES       OSSL_ALG_PARAM_PROPERTIES /* utf8 string */
#define OSSL_MAC_PARAM_SIZE             "size"                    /* size_t */
#define OSSL_MAC_PARAM_BLOCK_SIZE       "block-size"              /* size_t */
#define OSSL_MAC_PARAM_TLS_DATA_SIZE    "tls-data-size"           /* size_t */

/* Known MAC names */
#define OSSL_MAC_NAME_BLAKE2BMAC    "BLAKE2BMAC"
#define OSSL_MAC_NAME_BLAKE2SMAC    "BLAKE2SMAC"
#define OSSL_MAC_NAME_CMAC          "CMAC"
#define OSSL_MAC_NAME_GMAC          "GMAC"
#define OSSL_MAC_NAME_HMAC          "HMAC"
#define OSSL_MAC_NAME_KMAC128       "KMAC128"
#define OSSL_MAC_NAME_KMAC256       "KMAC256"
#define OSSL_MAC_NAME_POLY1305      "POLY1305"
#define OSSL_MAC_NAME_SIPHASH       "SIPHASH"

/* KDF / PRF parameters */
#define OSSL_KDF_PARAM_SECRET       "secret"    /* octet string */
#define OSSL_KDF_PARAM_KEY          "key"       /* octet string */
#define OSSL_KDF_PARAM_SALT         "salt"      /* octet string */
#define OSSL_KDF_PARAM_PASSWORD     "pass"      /* octet string */
#define OSSL_KDF_PARAM_PREFIX       "prefix"    /* octet string */
#define OSSL_KDF_PARAM_LABEL        "label"     /* octet string */
#define OSSL_KDF_PARAM_DATA         "data"      /* octet string */
#define OSSL_KDF_PARAM_DIGEST       OSSL_ALG_PARAM_DIGEST     /* utf8 string */
#define OSSL_KDF_PARAM_CIPHER       OSSL_ALG_PARAM_CIPHER     /* utf8 string */
#define OSSL_KDF_PARAM_MAC          OSSL_ALG_PARAM_MAC        /* utf8 string */
#define OSSL_KDF_PARAM_MAC_SIZE     "maclen"    /* size_t */
#define OSSL_KDF_PARAM_PROPERTIES   OSSL_ALG_PARAM_PROPERTIES /* utf8 string */
#define OSSL_KDF_PARAM_ITER         "iter"      /* unsigned int */
#define OSSL_KDF_PARAM_MODE         "mode"      /* utf8 string or int */
#define OSSL_KDF_PARAM_PKCS5        "pkcs5"     /* int */
#define OSSL_KDF_PARAM_UKM          "ukm"       /* octet string */
#define OSSL_KDF_PARAM_CEK_ALG      "cekalg"    /* utf8 string */
#define OSSL_KDF_PARAM_SCRYPT_N     "n"         /* uint64_t */
#define OSSL_KDF_PARAM_SCRYPT_R     "r"         /* uint32_t */
#define OSSL_KDF_PARAM_SCRYPT_P     "p"         /* uint32_t */
#define OSSL_KDF_PARAM_SCRYPT_MAXMEM "maxmem_bytes" /* uint64_t */
#define OSSL_KDF_PARAM_INFO         "info"      /* octet string */
#define OSSL_KDF_PARAM_SEED         "seed"      /* octet string */
#define OSSL_KDF_PARAM_SSHKDF_XCGHASH "xcghash" /* octet string */
#define OSSL_KDF_PARAM_SSHKDF_SESSION_ID "session_id" /* octet string */
#define OSSL_KDF_PARAM_SSHKDF_TYPE  "type"      /* int */
#define OSSL_KDF_PARAM_SIZE         "size"      /* size_t */
#define OSSL_KDF_PARAM_CONSTANT     "constant"  /* octet string */
#define OSSL_KDF_PARAM_PKCS12_ID    "id"        /* int */
#define OSSL_KDF_PARAM_KBKDF_USE_L  "use-l"             /* int */
#define OSSL_KDF_PARAM_KBKDF_USE_SEPARATOR  "use-separator"     /* int */
#define OSSL_KDF_PARAM_X942_ACVPINFO        "acvp-info"
#define OSSL_KDF_PARAM_X942_PARTYUINFO      "partyu-info"
#define OSSL_KDF_PARAM_X942_PARTYVINFO      "partyv-info"
#define OSSL_KDF_PARAM_X942_SUPP_PUBINFO    "supp-pubinfo"
#define OSSL_KDF_PARAM_X942_SUPP_PRIVINFO   "supp-privinfo"
#define OSSL_KDF_PARAM_X942_USE_KEYBITS     "use-keybits"

/* Known KDF names */
#define OSSL_KDF_NAME_HKDF           "HKDF"
#define OSSL_KDF_NAME_TLS1_3_KDF     "TLS13-KDF"
#define OSSL_KDF_NAME_PBKDF1         "PBKDF1"
#define OSSL_KDF_NAME_PBKDF2         "PBKDF2"
#define OSSL_KDF_NAME_SCRYPT         "SCRYPT"
#define OSSL_KDF_NAME_SSHKDF         "SSHKDF"
#define OSSL_KDF_NAME_SSKDF          "SSKDF"
#define OSSL_KDF_NAME_TLS1_PRF       "TLS1-PRF"
#define OSSL_KDF_NAME_X942KDF_ASN1   "X942KDF-ASN1"
#define OSSL_KDF_NAME_X942KDF_CONCAT "X942KDF-CONCAT"
#define OSSL_KDF_NAME_X963KDF        "X963KDF"
#define OSSL_KDF_NAME_KBKDF          "KBKDF"
#define OSSL_KDF_NAME_KRB5KDF        "KRB5KDF"

/* Known RAND names */
#define OSSL_RAND_PARAM_STATE                   "state"
#define OSSL_RAND_PARAM_STRENGTH                "strength"
#define OSSL_RAND_PARAM_MAX_REQUEST             "max_request"
#define OSSL_RAND_PARAM_TEST_ENTROPY            "test_entropy"
#define OSSL_RAND_PARAM_TEST_NONCE              "test_nonce"

/* RAND/DRBG names */
#define OSSL_DRBG_PARAM_RESEED_REQUESTS         "reseed_requests"
#define OSSL_DRBG_PARAM_RESEED_TIME_INTERVAL    "reseed_time_interval"
#define OSSL_DRBG_PARAM_MIN_ENTROPYLEN          "min_entropylen"
#define OSSL_DRBG_PARAM_MAX_ENTROPYLEN          "max_entropylen"
#define OSSL_DRBG_PARAM_MIN_NONCELEN            "min_noncelen"
#define OSSL_DRBG_PARAM_MAX_NONCELEN            "max_noncelen"
#define OSSL_DRBG_PARAM_MAX_PERSLEN             "max_perslen"
#define OSSL_DRBG_PARAM_MAX_ADINLEN             "max_adinlen"
#define OSSL_DRBG_PARAM_RESEED_COUNTER          "reseed_counter"
#define OSSL_DRBG_PARAM_RESEED_TIME             "reseed_time"
#define OSSL_DRBG_PARAM_PROPERTIES              OSSL_ALG_PARAM_PROPERTIES
#define OSSL_DRBG_PARAM_DIGEST                  OSSL_ALG_PARAM_DIGEST
#define OSSL_DRBG_PARAM_CIPHER                  OSSL_ALG_PARAM_CIPHER
#define OSSL_DRBG_PARAM_MAC                     OSSL_ALG_PARAM_MAC
#define OSSL_DRBG_PARAM_USE_DF                  "use_derivation_function"

/* DRBG call back parameters */
#define OSSL_DRBG_PARAM_ENTROPY_REQUIRED        "entropy_required"
#define OSSL_DRBG_PARAM_PREDICTION_RESISTANCE   "prediction_resistance"
#define OSSL_DRBG_PARAM_MIN_LENGTH              "minium_length"
#define OSSL_DRBG_PARAM_MAX_LENGTH              "maxium_length"
#define OSSL_DRBG_PARAM_RANDOM_DATA             "random_data"
#define OSSL_DRBG_PARAM_SIZE                    "size"

/* PKEY parameters */
/* Common PKEY parameters */
#define OSSL_PKEY_PARAM_BITS                "bits" /* integer */
#define OSSL_PKEY_PARAM_MAX_SIZE            "max-size" /* integer */
#define OSSL_PKEY_PARAM_SECURITY_BITS       "security-bits" /* integer */
#define OSSL_PKEY_PARAM_DIGEST              OSSL_ALG_PARAM_DIGEST
#define OSSL_PKEY_PARAM_CIPHER              OSSL_ALG_PARAM_CIPHER /* utf8 string */
#define OSSL_PKEY_PARAM_ENGINE              OSSL_ALG_PARAM_ENGINE /* utf8 string */
#define OSSL_PKEY_PARAM_PROPERTIES          OSSL_ALG_PARAM_PROPERTIES
#define OSSL_PKEY_PARAM_DEFAULT_DIGEST      "default-digest" /* utf8 string */
#define OSSL_PKEY_PARAM_MANDATORY_DIGEST    "mandatory-digest" /* utf8 string */
#define OSSL_PKEY_PARAM_PAD_MODE            "pad-mode"
#define OSSL_PKEY_PARAM_DIGEST_SIZE         "digest-size"
#define OSSL_PKEY_PARAM_MASKGENFUNC         "mgf"
#define OSSL_PKEY_PARAM_MGF1_DIGEST         "mgf1-digest"
#define OSSL_PKEY_PARAM_MGF1_PROPERTIES     "mgf1-properties"
#define OSSL_PKEY_PARAM_ENCODED_PUBLIC_KEY  "encoded-pub-key"
#define OSSL_PKEY_PARAM_GROUP_NAME          "group"
#define OSSL_PKEY_PARAM_DIST_ID             "distid"
#define OSSL_PKEY_PARAM_PUB_KEY             "pub"
#define OSSL_PKEY_PARAM_PRIV_KEY            "priv"

/* Diffie-Hellman/DSA Parameters */
#define OSSL_PKEY_PARAM_FFC_P               "p"
#define OSSL_PKEY_PARAM_FFC_G               "g"
#define OSSL_PKEY_PARAM_FFC_Q               "q"
#define OSSL_PKEY_PARAM_FFC_GINDEX          "gindex"
#define OSSL_PKEY_PARAM_FFC_PCOUNTER        "pcounter"
#define OSSL_PKEY_PARAM_FFC_SEED            "seed"
#define OSSL_PKEY_PARAM_FFC_COFACTOR        "j"
#define OSSL_PKEY_PARAM_FFC_H               "hindex"
#define OSSL_PKEY_PARAM_FFC_VALIDATE_PQ     "validate-pq"
#define OSSL_PKEY_PARAM_FFC_VALIDATE_G      "validate-g"
#define OSSL_PKEY_PARAM_FFC_VALIDATE_LEGACY "validate-legacy"

/* Diffie-Hellman params */
#define OSSL_PKEY_PARAM_DH_GENERATOR        "safeprime-generator"
#define OSSL_PKEY_PARAM_DH_PRIV_LEN         "priv_len"

/* Elliptic Curve Domain Parameters */
#define OSSL_PKEY_PARAM_EC_PUB_X     "qx"
#define OSSL_PKEY_PARAM_EC_PUB_Y     "qy"

/* Elliptic Curve Explicit Domain Parameters */
#define OSSL_PKEY_PARAM_EC_FIELD_TYPE                   "field-type"
#define OSSL_PKEY_PARAM_EC_P                            "p"
#define OSSL_PKEY_PARAM_EC_A                            "a"
#define OSSL_PKEY_PARAM_EC_B                            "b"
#define OSSL_PKEY_PARAM_EC_GENERATOR                    "generator"
#define OSSL_PKEY_PARAM_EC_ORDER                        "order"
#define OSSL_PKEY_PARAM_EC_COFACTOR                     "cofactor"
#define OSSL_PKEY_PARAM_EC_SEED                         "seed"
#define OSSL_PKEY_PARAM_EC_CHAR2_M                      "m"
#define OSSL_PKEY_PARAM_EC_CHAR2_TYPE                   "basis-type"
#define OSSL_PKEY_PARAM_EC_CHAR2_TP_BASIS               "tp"
#define OSSL_PKEY_PARAM_EC_CHAR2_PP_K1                  "k1"
#define OSSL_PKEY_PARAM_EC_CHAR2_PP_K2                  "k2"
#define OSSL_PKEY_PARAM_EC_CHAR2_PP_K3                  "k3"
#define OSSL_PKEY_PARAM_EC_DECODED_FROM_EXPLICIT_PARAMS "decoded-from-explicit"

/* Elliptic Curve Key Parameters */
#define OSSL_PKEY_PARAM_USE_COFACTOR_FLAG "use-cofactor-flag"
#define OSSL_PKEY_PARAM_USE_COFACTOR_ECDH \
    OSSL_PKEY_PARAM_USE_COFACTOR_FLAG

/* RSA Keys */
/*
 * n, e, d are the usual public and private key components
 *
 * rsa-num is the number of factors, including p and q
 * rsa-factor is used for each factor: p, q, r_i (i = 3, ...)
 * rsa-exponent is used for each exponent: dP, dQ, d_i (i = 3, ...)
 * rsa-coefficient is used for each coefficient: qInv, t_i (i = 3, ...)
 *
 * The number of rsa-factor items must be equal to the number of rsa-exponent
 * items, and the number of rsa-coefficients must be one less.
 * (the base i for the coefficients is 2, not 1, at least as implied by
 * RFC 8017)
 */
#define OSSL_PKEY_PARAM_RSA_N           "n"
#define OSSL_PKEY_PARAM_RSA_E           "e"
#define OSSL_PKEY_PARAM_RSA_D           "d"
#define OSSL_PKEY_PARAM_RSA_FACTOR      "rsa-factor"
#define OSSL_PKEY_PARAM_RSA_EXPONENT    "rsa-exponent"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT "rsa-coefficient"
#define OSSL_PKEY_PARAM_RSA_FACTOR1      OSSL_PKEY_PARAM_RSA_FACTOR"1"
#define OSSL_PKEY_PARAM_RSA_FACTOR2      OSSL_PKEY_PARAM_RSA_FACTOR"2"
#define OSSL_PKEY_PARAM_RSA_FACTOR3      OSSL_PKEY_PARAM_RSA_FACTOR"3"
#define OSSL_PKEY_PARAM_RSA_FACTOR4      OSSL_PKEY_PARAM_RSA_FACTOR"4"
#define OSSL_PKEY_PARAM_RSA_FACTOR5      OSSL_PKEY_PARAM_RSA_FACTOR"5"
#define OSSL_PKEY_PARAM_RSA_FACTOR6      OSSL_PKEY_PARAM_RSA_FACTOR"6"
#define OSSL_PKEY_PARAM_RSA_FACTOR7      OSSL_PKEY_PARAM_RSA_FACTOR"7"
#define OSSL_PKEY_PARAM_RSA_FACTOR8      OSSL_PKEY_PARAM_RSA_FACTOR"8"
#define OSSL_PKEY_PARAM_RSA_FACTOR9      OSSL_PKEY_PARAM_RSA_FACTOR"9"
#define OSSL_PKEY_PARAM_RSA_FACTOR10     OSSL_PKEY_PARAM_RSA_FACTOR"10"
#define OSSL_PKEY_PARAM_RSA_EXPONENT1    OSSL_PKEY_PARAM_RSA_EXPONENT"1"
#define OSSL_PKEY_PARAM_RSA_EXPONENT2    OSSL_PKEY_PARAM_RSA_EXPONENT"2"
#define OSSL_PKEY_PARAM_RSA_EXPONENT3    OSSL_PKEY_PARAM_RSA_EXPONENT"3"
#define OSSL_PKEY_PARAM_RSA_EXPONENT4    OSSL_PKEY_PARAM_RSA_EXPONENT"4"
#define OSSL_PKEY_PARAM_RSA_EXPONENT5    OSSL_PKEY_PARAM_RSA_EXPONENT"5"
#define OSSL_PKEY_PARAM_RSA_EXPONENT6    OSSL_PKEY_PARAM_RSA_EXPONENT"6"
#define OSSL_PKEY_PARAM_RSA_EXPONENT7    OSSL_PKEY_PARAM_RSA_EXPONENT"7"
#define OSSL_PKEY_PARAM_RSA_EXPONENT8    OSSL_PKEY_PARAM_RSA_EXPONENT"8"
#define OSSL_PKEY_PARAM_RSA_EXPONENT9    OSSL_PKEY_PARAM_RSA_EXPONENT"9"
#define OSSL_PKEY_PARAM_RSA_EXPONENT10   OSSL_PKEY_PARAM_RSA_EXPONENT"10"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT1 OSSL_PKEY_PARAM_RSA_COEFFICIENT"1"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT2 OSSL_PKEY_PARAM_RSA_COEFFICIENT"2"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT3 OSSL_PKEY_PARAM_RSA_COEFFICIENT"3"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT4 OSSL_PKEY_PARAM_RSA_COEFFICIENT"4"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT5 OSSL_PKEY_PARAM_RSA_COEFFICIENT"5"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT6 OSSL_PKEY_PARAM_RSA_COEFFICIENT"6"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT7 OSSL_PKEY_PARAM_RSA_COEFFICIENT"7"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT8 OSSL_PKEY_PARAM_RSA_COEFFICIENT"8"
#define OSSL_PKEY_PARAM_RSA_COEFFICIENT9 OSSL_PKEY_PARAM_RSA_COEFFICIENT"9"

/* RSA padding modes */
#define OSSL_PKEY_RSA_PAD_MODE_NONE    "none"
#define OSSL_PKEY_RSA_PAD_MODE_PKCSV15 "pkcs1"
#define OSSL_PKEY_RSA_PAD_MODE_OAEP    "oaep"
#define OSSL_PKEY_RSA_PAD_MODE_X931    "x931"
#define OSSL_PKEY_RSA_PAD_MODE_PSS     "pss"

/* RSA pss padding salt length */
#define OSSL_PKEY_RSA_PSS_SALT_LEN_DIGEST "digest"
#define OSSL_PKEY_RSA_PSS_SALT_LEN_MAX    "max"
#define OSSL_PKEY_RSA_PSS_SALT_LEN_AUTO   "auto"

/* Key generation parameters */
#define OSSL_PKEY_PARAM_RSA_BITS             OSSL_PKEY_PARAM_BITS
#define OSSL_PKEY_PARAM_RSA_PRIMES           "primes"
#define OSSL_PKEY_PARAM_RSA_DIGEST           OSSL_PKEY_PARAM_DIGEST
#define OSSL_PKEY_PARAM_RSA_DIGEST_PROPS     OSSL_PKEY_PARAM_PROPERTIES
#define OSSL_PKEY_PARAM_RSA_MASKGENFUNC      OSSL_PKEY_PARAM_MASKGENFUNC
#define OSSL_PKEY_PARAM_RSA_MGF1_DIGEST      OSSL_PKEY_PARAM_MGF1_DIGEST
#define OSSL_PKEY_PARAM_RSA_PSS_SALTLEN      "saltlen"

/* Key generation parameters */
#define OSSL_PKEY_PARAM_FFC_TYPE         "type"
#define OSSL_PKEY_PARAM_FFC_PBITS        "pbits"
#define OSSL_PKEY_PARAM_FFC_QBITS        "qbits"
#define OSSL_PKEY_PARAM_FFC_DIGEST       OSSL_PKEY_PARAM_DIGEST
#define OSSL_PKEY_PARAM_FFC_DIGEST_PROPS OSSL_PKEY_PARAM_PROPERTIES

#define OSSL_PKEY_PARAM_EC_ENCODING                "encoding" /* utf8_string */
#define OSSL_PKEY_PARAM_EC_POINT_CONVERSION_FORMAT "point-format"
#define OSSL_PKEY_PARAM_EC_GROUP_CHECK_TYPE        "group-check"
#define OSSL_PKEY_PARAM_EC_INCLUDE_PUBLIC          "include-public"

/* OSSL_PKEY_PARAM_EC_ENCODING values */
#define OSSL_PKEY_EC_ENCODING_EXPLICIT  "explicit"
#define OSSL_PKEY_EC_ENCODING_GROUP     "named_curve"

#define OSSL_PKEY_EC_POINT_CONVERSION_FORMAT_UNCOMPRESSED "uncompressed"
#define OSSL_PKEY_EC_POINT_CONVERSION_FORMAT_COMPRESSED   "compressed"
#define OSSL_PKEY_EC_POINT_CONVERSION_FORMAT_HYBRID       "hybrid"

#define OSSL_PKEY_EC_GROUP_CHECK_DEFAULT     "default"
#define OSSL_PKEY_EC_GROUP_CHECK_NAMED       "named"
#define OSSL_PKEY_EC_GROUP_CHECK_NAMED_NIST  "named-nist"

/* Key Exchange parameters */
#define OSSL_EXCHANGE_PARAM_PAD                   "pad" /* uint */
#define OSSL_EXCHANGE_PARAM_EC_ECDH_COFACTOR_MODE "ecdh-cofactor-mode" /* int */
#define OSSL_EXCHANGE_PARAM_KDF_TYPE              "kdf-type" /* utf8_string */
#define OSSL_EXCHANGE_PARAM_KDF_DIGEST            "kdf-digest" /* utf8_string */
#define OSSL_EXCHANGE_PARAM_KDF_DIGEST_PROPS      "kdf-digest-props" /* utf8_string */
#define OSSL_EXCHANGE_PARAM_KDF_OUTLEN            "kdf-outlen" /* size_t */
/* The following parameter is an octet_string on set and an octet_ptr on get */
#define OSSL_EXCHANGE_PARAM_KDF_UKM               "kdf-ukm"

/* Signature parameters */
#define OSSL_SIGNATURE_PARAM_ALGORITHM_ID       "algorithm-id"
#define OSSL_SIGNATURE_PARAM_PAD_MODE           OSSL_PKEY_PARAM_PAD_MODE
#define OSSL_SIGNATURE_PARAM_DIGEST             OSSL_PKEY_PARAM_DIGEST
#define OSSL_SIGNATURE_PARAM_PROPERTIES         OSSL_PKEY_PARAM_PROPERTIES
#define OSSL_SIGNATURE_PARAM_PSS_SALTLEN        "saltlen"
#define OSSL_SIGNATURE_PARAM_MGF1_DIGEST        OSSL_PKEY_PARAM_MGF1_DIGEST
#define OSSL_SIGNATURE_PARAM_MGF1_PROPERTIES    \
    OSSL_PKEY_PARAM_MGF1_PROPERTIES
#define OSSL_SIGNATURE_PARAM_DIGEST_SIZE        OSSL_PKEY_PARAM_DIGEST_SIZE

/* Asym cipher parameters */
#define OSSL_ASYM_CIPHER_PARAM_DIGEST                   OSSL_PKEY_PARAM_DIGEST
#define OSSL_ASYM_CIPHER_PARAM_PROPERTIES               OSSL_PKEY_PARAM_PROPERTIES
#define OSSL_ASYM_CIPHER_PARAM_ENGINE                   OSSL_PKEY_PARAM_ENGINE
#define OSSL_ASYM_CIPHER_PARAM_PAD_MODE                 OSSL_PKEY_PARAM_PAD_MODE
#define OSSL_ASYM_CIPHER_PARAM_MGF1_DIGEST              \
    OSSL_PKEY_PARAM_MGF1_DIGEST
#define OSSL_ASYM_CIPHER_PARAM_MGF1_DIGEST_PROPS        \
    OSSL_PKEY_PARAM_MGF1_PROPERTIES
#define OSSL_ASYM_CIPHER_PARAM_OAEP_DIGEST              OSSL_ALG_PARAM_DIGEST
#define OSSL_ASYM_CIPHER_PARAM_OAEP_DIGEST_PROPS        "digest-props"
/* The following parameter is an octet_string on set and an octet_ptr on get */
#define OSSL_ASYM_CIPHER_PARAM_OAEP_LABEL               "oaep-label"
#define OSSL_ASYM_CIPHER_PARAM_TLS_CLIENT_VERSION       "tls-client-version"
#define OSSL_ASYM_CIPHER_PARAM_TLS_NEGOTIATED_VERSION   "tls-negotiated-version"

/*
 * Encoder / decoder parameters
 */
#define OSSL_ENCODER_PARAM_CIPHER           OSSL_ALG_PARAM_CIPHER
#define OSSL_ENCODER_PARAM_PROPERTIES       OSSL_ALG_PARAM_PROPERTIES
/* Currently PVK only, but reusable for others as needed */
#define OSSL_ENCODER_PARAM_ENCRYPT_LEVEL    "encrypt-level"
#define OSSL_ENCODER_PARAM_SAVE_PARAMETERS  "save-parameters" /* integer */

#define OSSL_DECODER_PARAM_PROPERTIES       OSSL_ALG_PARAM_PROPERTIES

/* Passphrase callback parameters */
#define OSSL_PASSPHRASE_PARAM_INFO      "info"

/* Keygen callback parameters, from provider to libcrypto */
#define OSSL_GEN_PARAM_POTENTIAL            "potential" /* integer */
#define OSSL_GEN_PARAM_ITERATION            "iteration" /* integer */

/* ACVP Test parameters : These should not be used normally */
#define OSSL_PKEY_PARAM_RSA_TEST_XP1 "xp1"
#define OSSL_PKEY_PARAM_RSA_TEST_XP2 "xp2"
#define OSSL_PKEY_PARAM_RSA_TEST_XP  "xp"
#define OSSL_PKEY_PARAM_RSA_TEST_XQ1 "xq1"
#define OSSL_PKEY_PARAM_RSA_TEST_XQ2 "xq2"
#define OSSL_PKEY_PARAM_RSA_TEST_XQ  "xq"
#define OSSL_PKEY_PARAM_RSA_TEST_P1  "p1"
#define OSSL_PKEY_PARAM_RSA_TEST_P2  "p2"
#define OSSL_PKEY_PARAM_RSA_TEST_Q1  "q1"
#define OSSL_PKEY_PARAM_RSA_TEST_Q2  "q2"
#define OSSL_SIGNATURE_PARAM_KAT "kat"

/* KEM parameters */
#define OSSL_KEM_PARAM_OPERATION            "operation"

/* OSSL_KEM_PARAM_OPERATION values */
#define OSSL_KEM_PARAM_OPERATION_RSASVE     "RSASVE"

/* Capabilities */

/* TLS-GROUP Capability */
#define OSSL_CAPABILITY_TLS_GROUP_NAME              "tls-group-name"
#define OSSL_CAPABILITY_TLS_GROUP_NAME_INTERNAL     "tls-group-name-internal"
#define OSSL_CAPABILITY_TLS_GROUP_ID                "tls-group-id"
#define OSSL_CAPABILITY_TLS_GROUP_ALG               "tls-group-alg"
#define OSSL_CAPABILITY_TLS_GROUP_SECURITY_BITS     "tls-group-sec-bits"
#define OSSL_CAPABILITY_TLS_GROUP_IS_KEM            "tls-group-is-kem"
#define OSSL_CAPABILITY_TLS_GROUP_MIN_TLS           "tls-min-tls"
#define OSSL_CAPABILITY_TLS_GROUP_MAX_TLS           "tls-max-tls"
#define OSSL_CAPABILITY_TLS_GROUP_MIN_DTLS          "tls-min-dtls"
#define OSSL_CAPABILITY_TLS_GROUP_MAX_DTLS          "tls-max-dtls"

/*-
 * storemgmt parameters
 */

/*
 * Used by storemgmt_ctx_set_params():
 *
 * - OSSL_STORE_PARAM_EXPECT is an INTEGER, and the value is any of the
 *   OSSL_STORE_INFO numbers.  This is used to set the expected type of
 *   object loaded.
 *
 * - OSSL_STORE_PARAM_SUBJECT, OSSL_STORE_PARAM_ISSUER,
 *   OSSL_STORE_PARAM_SERIAL, OSSL_STORE_PARAM_FINGERPRINT,
 *   OSSL_STORE_PARAM_DIGEST, OSSL_STORE_PARAM_ALIAS
 *   are used as search criteria.
 *   (OSSL_STORE_PARAM_DIGEST is used with OSSL_STORE_PARAM_FINGERPRINT)
 */
#define OSSL_STORE_PARAM_EXPECT     "expect"       /* INTEGER */
#define OSSL_STORE_PARAM_SUBJECT    "subject" /* DER blob => OCTET_STRING */
#define OSSL_STORE_PARAM_ISSUER     "name" /* DER blob => OCTET_STRING */
#define OSSL_STORE_PARAM_SERIAL     "serial"       /* INTEGER */
#define OSSL_STORE_PARAM_DIGEST     "digest"       /* UTF8_STRING */
#define OSSL_STORE_PARAM_FINGERPRINT "fingerprint" /* OCTET_STRING */
#define OSSL_STORE_PARAM_ALIAS      "alias"        /* UTF8_STRING */

/* You may want to pass properties for the provider implementation to use */
#define OSSL_STORE_PARAM_PROPERTIES "properties"   /* utf8_string */
/* OSSL_DECODER input type if a decoder is used by the store */
#define OSSL_STORE_PARAM_INPUT_TYPE "input-type"   /* UTF8_STRING */

# ifdef __cplusplus
}
# endif

#endif
