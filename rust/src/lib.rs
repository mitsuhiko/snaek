extern crate cbindgen;

use std::io;
use std::mem;
use std::ptr;
use std::panic;
use std::error::Error;
use std::os::raw::c_char;
use std::ffi::{CStr, CString};
use cbindgen::{Config, Library, Language};

#[repr(C)]
pub struct BindgenError {
    pub failed: bool,
    pub msg: *mut c_char,
}

unsafe fn notify_err(err: Box<Error>, err_out: *mut BindgenError) {
    if !err_out.is_null() {
        (*err_out).failed = true;
        (*err_out).msg = CString::new(err.to_string()).unwrap().into_raw();
    }
}

unsafe fn landingpad<F: FnOnce() -> Result<T, Box<Error>> + panic::UnwindSafe, T>(
    f: F, err_out: *mut BindgenError) -> T
{
    match panic::catch_unwind(f) {
        Ok(rv) => {
            rv.map_err(|err| notify_err(err, err_out)).unwrap_or(mem::zeroed())
        }
        Err(err) => {
            let msg = match err.downcast_ref::<&'static str>() {
                Some(s) => *s,
                None => {
                    match err.downcast_ref::<String>() {
                        Some(s) => &**s,
                        None => "Box<Any>",
                    }
                }
            };
            notify_err(Box::new(io::Error::new(
                io::ErrorKind::Other, format!("native extension panicked: {}", msg))), err_out);
            mem::zeroed()
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn bindgen_init() {
    fn silent_panic_handler(_pi: &panic::PanicInfo) {}
    panic::set_hook(Box::new(silent_panic_handler));
}

#[no_mangle]
pub unsafe extern "C" fn bindgen_clear_err(err: *mut BindgenError) {
    if !(*err).msg.is_null() {
        CString::from_raw((*err).msg);
        (*err).msg = ptr::null_mut();
    }
}

#[no_mangle]
pub unsafe extern "C" fn bindgen_generate_headers(
    path: *const c_char, err_out: *mut BindgenError) -> *mut c_char
{
    landingpad(|| {
        let mut config: Config = Default::default();
        config.language = Language::C;
        let path = CStr::from_ptr(path).to_str().unwrap();
        let mut out: Vec<u8> = vec![];
        Library::load(&path, &config)
            .generate()?
            .write(&mut out);
        Ok(CString::new(out)?.into_raw())
    }, err_out)
}

#[no_mangle]
pub unsafe extern "C" fn bindgen_free_string(
    s: *mut c_char)
{
    if !s.is_null() {
        CString::from_raw(s);
    }
}
