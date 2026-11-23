package br.com.socialvault.app;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.atomic.AtomicBoolean;

/** Bounded HTTPS image transfer and transactional MediaStore publication. */
final class PhotoTransfer {
    private static final int MAX_PREVIEW_BYTES = 8 * 1024 * 1024;
    private static final int MAX_PHOTO_BYTES = 32 * 1024 * 1024;
    private static final String USER_AGENT = "Mozilla/5.0 (Linux; Android 14) SocialVault/0.4";

    static class Cancelled extends IOException { Cancelled() { super("Operação cancelada."); } }
    interface Progress { void onBytes(long done, long total); }

    private PhotoTransfer() { }

    private static HttpURLConnection connect(String source) throws IOException {
        if (!PhotoUrl.isSafe(source)) throw new IOException("URL de imagem inválida ou insegura.");
        HttpURLConnection connection = (HttpURLConnection) new URL(source).openConnection();
        connection.setRequestProperty("User-Agent", USER_AGENT);
        connection.setRequestProperty("Referer", "https://www.tiktok.com/");
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(20000);
        connection.setInstanceFollowRedirects(true);
        connection.connect();
        if (!PhotoUrl.isSafe(connection.getURL().toString())) {
            connection.disconnect();
            throw new IOException("O servidor redirecionou para um endereço não permitido.");
        }
        if (connection.getResponseCode() != 200) {
            int code = connection.getResponseCode();
            connection.disconnect();
            throw new IOException("Não foi possível acessar a foto (HTTP " + code + ").");
        }
        String type = connection.getContentType();
        if (type != null && (type.startsWith("text/") || type.contains("html") || type.contains("json"))) {
            connection.disconnect();
            throw new IOException("A publicação não disponibilizou um arquivo de imagem.");
        }
        return connection;
    }

    static Bitmap preview(String source) throws IOException {
        HttpURLConnection connection = connect(source);
        try (InputStream in = connection.getInputStream();
             ByteArrayOutputStream result = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[32768];
            int received;
            while ((received = in.read(buffer)) != -1) {
                if (result.size() + received > MAX_PREVIEW_BYTES) {
                    throw new IOException("Imagem acima do limite de prévia de 8 MB.");
                }
                result.write(buffer, 0, received);
            }
            byte[] data = result.toByteArray();
            BitmapFactory.Options bounds = new BitmapFactory.Options();
            bounds.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
            if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw new IOException("Imagem inválida.");
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inSampleSize = 1;
            while (bounds.outWidth / options.inSampleSize > 420 || bounds.outHeight / options.inSampleSize > 420) {
                options.inSampleSize *= 2;
            }
            Bitmap bitmap = BitmapFactory.decodeByteArray(data, 0, data.length, options);
            if (bitmap == null) throw new IOException("Não foi possível decodificar a foto.");
            return bitmap;
        } finally {
            connection.disconnect();
        }
    }

    private static String detectMime(File file) throws IOException {
        byte[] first = new byte[16];
        try (InputStream in = new FileInputStream(file)) {
            if (in.read(first) < 12) throw new IOException("Foto vazia ou incompleta.");
        }
        if ((first[0] & 255) == 0xFF && (first[1] & 255) == 0xD8) return "image/jpeg";
        if ((first[0] & 255) == 0x89 && first[1] == 'P' && first[2] == 'N' && first[3] == 'G') return "image/png";
        if (first[0] == 'R' && first[1] == 'I' && first[2] == 'F' && first[3] == 'F'
            && first[8] == 'W' && first[9] == 'E' && first[10] == 'B' && first[11] == 'P') return "image/webp";
        throw new IOException("Formato de imagem inesperado (aceitos JPEG, PNG e WebP).");
    }

    static Uri save(Context context, String source, String postId, int index,
                    AtomicBoolean cancelled, Progress callback) throws IOException {
        if (cancelled.get()) throw new Cancelled();
        File tmp = File.createTempFile("sv-photo-", ".part", context.getCacheDir());
        try {
            HttpURLConnection connection = connect(source);
            try (InputStream in = connection.getInputStream();
                 OutputStream out = new FileOutputStream(tmp)) {
                byte[] buffer = new byte[65536];
                long size = 0;
                long length = connection.getContentLengthLong();
                if (length > MAX_PHOTO_BYTES) throw new IOException("A imagem ultrapassa o limite de 32 MB.");
                int read;
                while ((read = in.read(buffer)) != -1) {
                    if (cancelled.get()) throw new Cancelled();
                    size += read;
                    if (size > MAX_PHOTO_BYTES) throw new IOException("A imagem ultrapassa o limite de 32 MB.");
                    out.write(buffer, 0, read);
                    if (callback != null) callback.onBytes(size, length);
                }
                if (size == 0) throw new IOException("Arquivo de imagem vazio.");
            } finally {
                connection.disconnect();
            }
            if (cancelled.get()) throw new Cancelled();
            String mime = detectMime(tmp);
            String suffix = "image/jpeg".equals(mime) ? "jpg" : "image/png".equals(mime) ? "png" : "webp";
            String cleanId = postId == null ? "post" : postId.replaceAll("[^0-9A-Za-z_-]", "");
            if (cleanId.isEmpty()) cleanId = "post";
            if (cleanId.length() > 40) cleanId = cleanId.substring(0, 40);
            String fileName = "SV_" + cleanId + "_" + String.format(java.util.Locale.US, "%02d", index) + "_" + System.currentTimeMillis() + "." + suffix;
            return publish(context, tmp, mime, fileName, cancelled);
        } finally {
            if (tmp.exists()) tmp.delete();
        }
    }

    private static Uri publish(Context context, File source, String mime, String name,
                               AtomicBoolean cancelled) throws IOException {
        ContentResolver resolver = context.getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
        values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/SocialVault");
        values.put(MediaStore.MediaColumns.IS_PENDING, 1);
        Uri uri = resolver.insert(MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values);
        if (uri == null) throw new IOException("O Android recusou salvar a foto.");
        try {
            try (InputStream in = new FileInputStream(source);
                 OutputStream out = resolver.openOutputStream(uri, "w")) {
                if (out == null) throw new IOException("Não foi possível escrever na galeria.");
                byte[] buffer = new byte[65536];
                int count;
                while ((count = in.read(buffer)) != -1) {
                    if (cancelled.get()) throw new Cancelled();
                    out.write(buffer, 0, count);
                }
            }
            if (cancelled.get()) throw new Cancelled();
            ContentValues finish = new ContentValues();
            finish.put(MediaStore.MediaColumns.IS_PENDING, 0);
            if (resolver.update(uri, finish, null, null) != 1) throw new IOException("Falha ao publicar a foto.");
            return uri;
        } catch (Exception error) {
            resolver.delete(uri, null, null);
            if (error instanceof IOException) throw (IOException) error;
            throw new IOException("Falha ao salvar na galeria.", error);
        }
    }
}
