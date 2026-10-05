//! Screenshots on Linux, the default Pictures folder, and the folder picker.
//!
//! Windows copies the pixels on screen. Wayland lets no app read the screen,
//! so here the page renders itself instead: WebKitGTK's snapshot of the
//! webview, cropped to the area the page asked for. It shows the meter on a
//! solid background rather than over the game behind it, which a screen copy
//! would. The folder picker is GTK's native one, which goes through the
//! desktop's portal on Wayland.

use std::path::{Path, PathBuf};
use std::time::Duration;

use gtk::prelude::*;
use webkit2gtk::{SnapshotOptions, SnapshotRegion, WebViewExt};

use super::dialog::on_gtk_thread;
use crate::platform::screenshot::encode_png;

/// The colour transparent parts of the page are laid on: the meter's own
/// dark backdrop, so a pasted screenshot reads as it does over the game.
const BACKDROP: [u8; 3] = [12, 14, 20];

/// Top-down RGBA rows.
struct Image {
    width: u32,
    height: u32,
    rgba: Vec<u8>,
}

impl Image {
    fn crop(&self, left: u32, top: u32, width: u32, height: u32) -> Image {
        let left = left.min(self.width);
        let top = top.min(self.height);
        let width = width.min(self.width - left);
        let height = height.min(self.height - top);
        let mut rgba = Vec::with_capacity((width * height * 4) as usize);
        for row in top..top + height {
            let start = ((row * self.width + left) * 4) as usize;
            rgba.extend_from_slice(&self.rgba[start..start + (width * 4) as usize]);
        }
        Image { width, height, rgba }
    }

    /// `left` and `right` side by side, top-aligned, on the backdrop.
    fn beside(left: &Image, right: &Image) -> Image {
        const GAP: u32 = 8;
        let width = left.width + GAP + right.width;
        let height = left.height.max(right.height);
        let mut rgba = [BACKDROP[0], BACKDROP[1], BACKDROP[2], 255].repeat((width * height) as usize);
        for (img, x0) in [(left, 0), (right, left.width + GAP)] {
            for row in 0..img.height {
                let src = (row * img.width * 4) as usize;
                let dst = ((row * width + x0) * 4) as usize;
                rgba[dst..dst + (img.width * 4) as usize]
                    .copy_from_slice(&img.rgba[src..src + (img.width * 4) as usize]);
            }
        }
        Image { width, height, rgba }
    }
}

/// Cairo's ARGB32 (premultiplied, native byte order) to RGBA, laid on the
/// backdrop so the result is opaque.
fn surface_to_image(surface: gtk::cairo::Surface) -> Option<Image> {
    let image = gtk::cairo::ImageSurface::try_from(surface).ok()?;
    image.flush();
    let (width, height, stride) = (image.width(), image.height(), image.stride());
    if width <= 0 || height <= 0 {
        return None;
    }
    let mut rgba = Vec::with_capacity((width * height * 4) as usize);
    image
        .with_data(|data| {
            for row in 0..height {
                let line = &data[(row * stride) as usize..];
                for px in line.chunks_exact(4).take(width as usize) {
                    let argb = u32::from_ne_bytes([px[0], px[1], px[2], px[3]]);
                    let alpha = argb >> 24;
                    let channel = |shift: u32, back: u8| {
                        // Premultiplied colour, plus the backdrop showing through.
                        let c = (argb >> shift) & 0xff;
                        (c + (u32::from(back) * (255 - alpha)) / 255).min(255) as u8
                    };
                    rgba.extend_from_slice(&[channel(16, BACKDROP[0]), channel(8, BACKDROP[1]), channel(0, BACKDROP[2]), 255]);
                }
            }
        })
        .ok()?;
    Some(Image { width: width as u32, height: height as u32, rgba })
}

/// What `window`'s page shows, rendered by WebKit, and how many image pixels
/// make one CSS pixel. Blocking: the snapshot is taken on the GTK thread.
fn snapshot(window: &tauri::WebviewWindow) -> Option<(Image, f64)> {
    let (tx, rx) = std::sync::mpsc::channel();
    window
        .with_webview(move |webview| {
            webview.inner().snapshot(
                SnapshotRegion::Visible,
                SnapshotOptions::NONE,
                None::<&gtk::gio::Cancellable>,
                move |result| {
                    let _ = tx.send(result.ok().and_then(surface_to_image));
                },
            );
        })
        .ok()?;
    let image = rx.recv_timeout(Duration::from_secs(5)).ok().flatten()?;
    // The page's CSS pixels are the window's logical pixels; the image may be
    // drawn at the display's scale, so measure rather than assume.
    let logical_width = window.inner_size().ok()?.width as f64 / window.scale_factor().ok()?;
    let ratio = if logical_width > 0.0 { image.width as f64 / logical_width } else { 1.0 };
    Some((image, ratio))
}

fn to_clipboard(image: &Image) -> bool {
    let (width, height, rgba) = (image.width as i32, image.height as i32, image.rgba.clone());
    on_gtk_thread(move || {
        let pixbuf = gtk::gdk_pixbuf::Pixbuf::from_bytes(
            &gtk::glib::Bytes::from_owned(rgba),
            gtk::gdk_pixbuf::Colorspace::Rgb,
            true,
            8,
            width,
            height,
            width * 4,
        );
        let clipboard = gtk::Clipboard::get(&gtk::gdk::SELECTION_CLIPBOARD);
        clipboard.set_image(&pixbuf);
        // Hand it to the clipboard manager so it outlives the meter.
        clipboard.store();
        true
    })
    .unwrap_or(false)
}

fn to_file(image: &Image, path: &Path) -> bool {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    std::fs::write(path, encode_png(image.width, image.height, &image.rgba)).is_ok()
}

/// Capture a CSS-pixel rect of `caller` (plus all of `meter`, if given, beside
/// it: Wayland does not say where windows are, so they cannot be placed as on
/// screen), put it on the clipboard and optionally write it to `png_path`.
/// Blocking. Returns (clipboard ok, file ok).
#[allow(clippy::too_many_arguments)]
pub fn capture(
    caller: &tauri::WebviewWindow,
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    _scale: f64,
    meter: Option<&tauri::WebviewWindow>,
    png_path: Option<&Path>,
) -> (bool, bool) {
    let Some((page, ratio)) = snapshot(caller) else {
        tracing::warn!("Screenshot: WebKit gave no snapshot");
        return (false, false);
    };
    let px = |v: f64| (v * ratio).round().max(0.0) as u32;
    let mut image = page.crop(px(x), px(y), px(width), px(height));
    if let Some((meter_page, _)) = meter.and_then(snapshot) {
        image = Image::beside(&meter_page, &image);
    }
    let clipboard = to_clipboard(&image);
    let file = png_path.is_some_and(|path| to_file(&image, path));
    (clipboard, file)
}

/// `~/Pictures/A2Tools DPS Meter` (or the XDG Pictures folder wherever it is).
pub fn default_folder() -> Option<PathBuf> {
    let pictures = gtk::glib::user_special_dir(gtk::glib::UserDirectory::Pictures)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join("Pictures")))?;
    Some(pictures.join("A2Tools DPS Meter"))
}

/// The desktop's folder picker. Blocks until the player chooses or cancels.
pub fn pick_folder(_owner: &tauri::WebviewWindow, start_in: Option<&str>) -> Option<String> {
    let start_in = start_in.filter(|s| !s.is_empty()).map(PathBuf::from);
    on_gtk_thread(move || {
        let dialog = gtk::FileChooserNative::new(
            Some("Choose a folder for screenshots"),
            None::<&gtk::Window>,
            gtk::FileChooserAction::SelectFolder,
            None,
            None,
        );
        if let Some(start) = start_in {
            let _ = dialog.set_current_folder(start);
        }
        let chosen = (dialog.run() == gtk::ResponseType::Accept)
            .then(|| dialog.filename())
            .flatten();
        chosen.map(|path| path.display().to_string())
    })
    .flatten()
}
