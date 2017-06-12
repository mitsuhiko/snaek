/* Generated with cbindgen:0.1.10 */

#include <stdint.h>
#include <stdbool.h>

typedef struct {
  bool failed;
  char *msg;
} BindgenError;

void cbindgen_clear_err(BindgenError *err);

void cbindgen_free_string(char *s);

char* cbindgen_generate_headers(const char *path, BindgenError *err_out);

void cbindgen_init();
