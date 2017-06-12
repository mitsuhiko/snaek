/* Generated with cbindgen:0.1.10 */

#include <stdint.h>
#include <stdbool.h>

typedef struct {
  bool failed;
  char *msg;
} BindgenError;

void bindgen_clear_err(BindgenError *err);

void bindgen_free_string(char *s);

char* bindgen_generate_headers(const char *path, BindgenError *err_out);

void bindgen_init();
