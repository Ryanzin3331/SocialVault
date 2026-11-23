package br.com.socialvault.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.TextView;
import android.widget.Toast;

import com.arthenica.ffmpegkit.FFmpegKit;
import com.arthenica.ffmpegkit.ReturnCode;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * SocialVault Fase B: interface nativa, link via ACTION_SEND, motor Python,
 * conversão MP3 e publicação no MediaStore. Sem login, sem anúncios.
 */
public final class MainActivity extends Activity {
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final AtomicBoolean cancelled = new AtomicBoolean(false);
    private EditText linkInput;
    private RadioButton mp3Radio;
    private Button downloadButton, cancelButton, openButton, shareButton;
    private TextView statusText, progressLabel, savedText, formatInfo;
    private ProgressBar progressBar;
    private boolean busy = false;
    private Uri savedUri;
    private String savedMime = "video/mp4";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        View root = findViewById(R.id.rootScroll);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets safe = insets.getInsets(WindowInsets.Type.systemBars());
                v.setPadding(0, safe.top, 0, safe.bottom);
            } else {
                v.setPadding(0, insets.getSystemWindowInsetTop(), 0, insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        linkInput = findViewById(R.id.linkInput);
        mp3Radio = findViewById(R.id.mp3Radio);
        downloadButton = findViewById(R.id.downloadButton);
        cancelButton = findViewById(R.id.cancelButton);
        openButton = findViewById(R.id.openButton);
        shareButton = findViewById(R.id.shareButton);
        progressBar = findViewById(R.id.progressBar);
        statusText = findViewById(R.id.statusText);
        progressLabel = findViewById(R.id.progressLabel);
        savedText = findViewById(R.id.savedText);
        formatInfo = findViewById(R.id.formatInfo);

        downloadButton.setOnClickListener(v -> beginDownload());
        cancelButton.setOnClickListener(v -> {
            cancelled.set(true);
            setStatus("Cancelando, aguarde a próxima etapa…");
            // FFmpeg também pode estar processando o arquivo nesta etapa.
            FFmpegKit.cancel();
        });
        mp3Radio.setOnClickListener(v -> formatInfo.setText("MP3: áudio convertido localmente para 192 kbps."));
        findViewById(R.id.mp4Radio).setOnClickListener(v -> formatInfo.setText(
            "MP4: melhor arquivo compatível disponível (sem reencodar)."));
        openButton.setOnClickListener(v -> sendFile(false));
        shareButton.setOnClickListener(v -> sendFile(true));
        restoreLastDownload();
        consumeSharedIntent(getIntent());
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        consumeSharedIntent(intent);
    }

    private void consumeSharedIntent(Intent intent) {
        if (intent == null || !Intent.ACTION_SEND.equals(intent.getAction())) return;
        if (!"text/plain".equals(intent.getType())) return;
        String text = intent.getStringExtra(Intent.EXTRA_TEXT);
        String url = TikTokLink.extract(text);
        if (url != null) {
            linkInput.setText(url);
            linkInput.setSelection(url.length());
            if (!busy) setStatus("Link recebido! Escolha MP4 ou MP3 e toque em Baixar.");
        } else if (!busy) {
            setStatus("O texto compartilhado não contém um link TikTok reconhecido.");
        }
    }

    private void beginDownload() {
        if (busy) return;
        String url = TikTokLink.extract(linkInput.getText().toString());
        if (url == null) {
            linkInput.setError("Compartilhe ou cole um link oficial do TikTok.");
            return;
        }
        final String mode = mp3Radio.isChecked() ? "mp3" : "mp4";
        busy = true;
        cancelled.set(false);
        downloadButton.setEnabled(false);
        cancelButton.setVisibility(View.VISIBLE);
        linkInput.setEnabled(false);
        progressBar.setProgress(0);
        progressBar.setIndeterminate(false);
        progressLabel.setText("0%");
        setStatus("Preparando motor de download…");
        io.execute(() -> runDownload(url, mode));
    }

    public static class ProgressListener {
        private final AtomicBoolean cancellation;
        private final MainActivity activity;
        private int lastUiPercent = -999;
        private long lastUiAt = 0;
        ProgressListener(MainActivity activity, AtomicBoolean cancellation) {
            this.activity = activity;
            this.cancellation = cancellation;
        }
        public boolean isCancelled() { return cancellation.get(); }
        public void onProgress(String stage, int percent) {
            long now = android.os.SystemClock.elapsedRealtime();
            if ("downloading".equals(stage) && percent == lastUiPercent && now - lastUiAt < 250) return;
            if ("downloading".equals(stage) && percent >= 0 && lastUiPercent >= 0
                && percent - lastUiPercent < 2 && now - lastUiAt < 250) return;
            lastUiAt = now;
            lastUiPercent = percent;
            activity.runOnUiThread(() -> {
                if ("starting".equals(stage)) activity.setStatus("Conectando ao TikTok…");
                else if ("downloading".equals(stage)) activity.setStatus("Baixando arquivo…");
                else activity.setStatus("Download recebido. Processando…");
                activity.progressBar.setIndeterminate(percent < 0);
                if (percent >= 0) {
                    activity.progressBar.setProgress(percent);
                    activity.progressLabel.setText(percent + "%");
                } else activity.progressLabel.setText("Obtendo dados…");
            });
        }
    }

    private void runDownload(String url, String mode) {
        File work = null;
        try {
            work = new File(getCacheDir(), "job-" + System.currentTimeMillis());
            if (!work.mkdirs()) throw new IOException("Não foi possível criar diretório temporário.");
            Python py = Python.getInstance();
            PyObject bridge = py.getModule("android_bridge");
            String path = bridge.callAttr("download_source", url, mode, work.getAbsolutePath(),
                new ProgressListener(this, cancelled)).toString();
            if (cancelled.get()) throw new InterruptedException("Cancelado");
            File source = new File(path);
            File finalFile = source;
            if ("mp3".equals(mode)) {
                runOnUiThread(() -> {
                    setStatus("Convertendo áudio para MP3…");
                    progressBar.setIndeterminate(true);
                    progressLabel.setText("Convertendo localmente");
                });
                finalFile = new File(work, "converted.mp3");
                String[] command = { "-hide_banner", "-loglevel", "error", "-y",
                    "-i", source.getAbsolutePath(), "-vn", "-codec:a", "libmp3lame",
                    "-b:a", "192k", finalFile.getAbsolutePath() };
                com.arthenica.ffmpegkit.FFmpegSession session = FFmpegKit.executeWithArguments(command);
                if (cancelled.get()) throw new InterruptedException("Cancelado");
                if (!ReturnCode.isSuccess(session.getReturnCode()) || !finalFile.isFile() || finalFile.length() == 0) {
                    throw new IOException("Não foi possível converter a fonte de áudio em MP3.");
                }
            }
            if (cancelled.get()) throw new InterruptedException("Cancelado");
            File publish = finalFile;
            runOnUiThread(() -> {
                setStatus("Salvando no armazenamento do Android…");
                progressBar.setIndeterminate(true);
                progressLabel.setText("Salvando arquivo");
            });
            boolean audio = mode.equals("mp3");
            String mime = audio ? "audio/mpeg" : "video/mp4";
            String name = "SV_" + System.currentTimeMillis() + "." + (audio ? "mp3" : "mp4");
            Uri uri = publishToMediaStore(publish, name, mime, audio);
            if (cancelled.get()) {
                getContentResolver().delete(uri, null, null);
                throw new InterruptedException("Cancelado");
            }
            runOnUiThread(() -> {
                savedUri = uri;
                savedMime = mime;
                savedText.setText(name + "\n" + (audio ? "Música/SocialVault" : "Filmes/SocialVault"));
                openButton.setEnabled(true);
                shareButton.setEnabled(true);
                getPreferences(MODE_PRIVATE).edit()
                    .putString("last_uri", uri.toString())
                    .putString("last_mime", mime)
                    .putString("last_name", name)
                    .apply();
                progressBar.setIndeterminate(false);
                progressBar.setProgress(100);
                progressLabel.setText("100%");
                setStatus("✅ Salvo com sucesso!");
            });
        } catch (Exception ex) {
            String detail = cancelled.get() ? "Download cancelado." : "Falha: " + friendlyError(ex);
            runOnUiThread(() -> {
                setStatus(detail);
                progressBar.setIndeterminate(false);
                progressBar.setProgress(0);
                progressLabel.setText("—");
            });
        } finally {
            if (work != null) removeTree(work);
            runOnUiThread(() -> {
                busy = false;
                downloadButton.setEnabled(true);
                cancelButton.setVisibility(View.GONE);
                linkInput.setEnabled(true);
            });
        }
    }

    private Uri publishToMediaStore(File file, String name, String mime, boolean audio) throws IOException, InterruptedException {
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
        values.put(MediaStore.MediaColumns.RELATIVE_PATH,
            (audio ? Environment.DIRECTORY_MUSIC : Environment.DIRECTORY_MOVIES) + "/SocialVault");
        values.put(MediaStore.MediaColumns.IS_PENDING, 1);
        Uri collection = audio
            ? MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
            : MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        Uri target = getContentResolver().insert(collection, values);
        if (target == null) throw new IOException("O sistema recusou a criação do arquivo.");
        try {
            try (InputStream input = new FileInputStream(file);
                 OutputStream output = getContentResolver().openOutputStream(target, "w")) {
                if (output == null) throw new IOException("Não foi possível abrir o armazenamento.");
                byte[] buffer = new byte[256 * 1024];
                int read;
                while ((read = input.read(buffer)) != -1) {
                    if (cancelled.get()) throw new InterruptedException("Cancelado");
                    output.write(buffer, 0, read);
                }
                output.flush();
            }
            if (cancelled.get()) throw new InterruptedException("Cancelado");
            ContentValues finish = new ContentValues();
            finish.put(MediaStore.MediaColumns.IS_PENDING, 0);
            if (getContentResolver().update(target, finish, null, null) != 1)
                throw new IOException("Não foi possível publicar o arquivo.");
            return target;
        } catch (Exception error) {
            getContentResolver().delete(target, null, null);
            if (error instanceof InterruptedException) throw (InterruptedException) error;
            if (error instanceof IOException) throw (IOException) error;
            throw new IOException("Erro ao salvar o arquivo no Android.", error);
        }
    }

    private void restoreLastDownload() {
        String uri = getPreferences(MODE_PRIVATE).getString("last_uri", null);
        if (uri == null) return;
        savedUri = Uri.parse(uri);
        savedMime = getPreferences(MODE_PRIVATE).getString("last_mime", "video/mp4");
        String name = getPreferences(MODE_PRIVATE).getString("last_name", "Último arquivo");
        savedText.setText(name);
        openButton.setEnabled(true);
        shareButton.setEnabled(true);
    }

    private void sendFile(boolean share) {
        if (savedUri == null) return;
        try {
            Intent intent = new Intent(share ? Intent.ACTION_SEND : Intent.ACTION_VIEW);
            if (share) {
                intent.setType(savedMime);
                intent.putExtra(Intent.EXTRA_STREAM, savedUri);
                intent.setClipData(ClipData.newUri(getContentResolver(), "SocialVault", savedUri));
            } else {
                intent.setDataAndType(savedUri, savedMime);
            }
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(intent, share ? "Compartilhar mídia" : "Abrir arquivo"));
        } catch (Exception ex) {
            Toast.makeText(this, "Não foi possível abrir o arquivo. Verifique se ele ainda existe.", Toast.LENGTH_LONG).show();
        }
    }

    private static void removeTree(File path) {
        if (!path.exists()) return;
        if (path.isDirectory()) {
            File[] children = path.listFiles();
            if (children != null) for (File child : children) removeTree(child);
        }
        path.delete();
    }
    private static String friendlyError(Exception ex) {
        String msg = ex.getMessage();
        if (msg == null || msg.trim().isEmpty()) return "Não foi possível concluir. Tente outro vídeo permitido.";
        String compact = msg.replaceAll("\\s+", " ");
        return compact.length() > 200 ? compact.substring(0, 200) + "…" : compact;
    }
    private void setStatus(String message) { statusText.setText(message); }

    @Override protected void onDestroy() {
        cancelled.set(true);
        FFmpegKit.cancel();
        io.shutdownNow();
        super.onDestroy();
    }
}
