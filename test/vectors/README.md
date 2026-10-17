# Vendored test vectors

`acvp_mlkem_keygen.json` and `acvp_mlkem_encapdecap.json` are the official NIST ACVP ML-KEM vectors,
filtered to the ML-KEM-512 and ML-KEM-768 test groups (ML-KEM-1024 removed, otherwise unchanged).

Source: https://github.com/usnistgov/ACVP-Server, commit `975de31eb83d87039ec88934fdc47d8c312b892d`
- `gen-val/json-files/ML-KEM-keyGen-FIPS203/internalProjection.json`
- `gen-val/json-files/ML-KEM-encapDecap-FIPS203/internalProjection.json`

`internalProjection.json` holds the prompts together with the expected results (d, z -> ek, dk; ek, m -> c, k;
dk, c -> k; and the key-check verdicts).
