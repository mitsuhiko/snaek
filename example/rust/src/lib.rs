#[repr(C)]
pub struct Point {
    pub x: f32,
    pub y: f32,
}

#[no_mangle]
pub unsafe extern "C" fn example_get_origin() -> Point {
    Point { x: 0.0, y: 0.0 }
}
