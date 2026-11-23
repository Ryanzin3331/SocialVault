package br.com.socialvault.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.chaquo.python.Python;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Photo Mode: single TikTok carousel inspection, preview, selection, gallery save. */
public final class PhotoActivity extends Activity {
    private final ExecutorService work = Executors.newSingleThreadExecutor();
    private final ExecutorService previews = Executors.newFixedThreadPool(2);
    private final AtomicBoolean cancelled = new AtomicBoolean(false);
    private final List<Photo> photos = new ArrayList<>();
    private Button saveButton, cancelButton, selectAll, clearAll;
    private TextView status, title, hint;
    private ProgressBar loading;
    private LinearLayout cards;
    private boolean active = false;
    private boolean destroyed = false;
    private String postId = "post";

    private static final class Photo {
        final String url;
        final int index, width, height;
        CheckBox check;
        ImageView preview;
        Bitmap bitmap;
        Photo(String url, int index, int width, int height) {
            this.url = url;
            this.index = index;
            this.width = width;
            this.height = height;
        }
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_photos);
        title = findViewById(R.id.photoTitle);
        hint = findViewById(R.id.photoHint);
        status = findViewById(R.id.photoStatus);
        loading = findViewById(R.id.photoLoading);
        cards = findViewById(R.id.photoCardsContainer);
        saveButton = findViewById(R.id.savePhotos);
        cancelButton = findViewById(R.id.cancelPhotos);
        selectAll = findViewById(R.id.selectAllPhotos);
        clearAll = findViewById(R.id.clearPhotos);
        findViewById(R.id.photoBackButton).setOnClickListener(v -> finish());
        saveButton.setOnClickListener(v -> saveSelected());
        cancelButton.setOnClickListener(v -> { cancelled.set(true); status.setText("Cancelando…"); });
        selectAll.setOnClickListener(v -> checkAll(true));
        clearAll.setOnClickListener(v -> checkAll(false));
        String url = TikTokLink.extract(getIntent().getStringExtra("post_url"));
        if (url == null) {
            loading.setVisibility(View.GONE);
            status.setText("Link TikTok inválido.");
            return;
        }
        inspect(url);
    }

    private void inspect(String url) {
        active = true;
        status.setText("Analisando fotos da publicação…");
        work.execute(() -> {
            try {
                String json = Python.getInstance().getModule("photo_bridge")
                    .callAttr("inspect_post", url).toString();
                JSONObject data = new JSONObject(json);
                if (!"photos".equals(data.optString("kind"))) {
                    runOnUiThread(() -> {
                        loading.setVisibility(View.GONE);
                        title.setText("Esta publicação é um vídeo");
                        status.setText("Volte para baixar MP4 ou MP3.");
                        active = false;
                    });
                    return;
                }
                JSONArray items = data.getJSONArray("images");
                String id = data.optString("post_id", "post");
                String postTitle = data.optString("title", "Fotos do TikTok");
                List<Photo> collected = new ArrayList<>();
                for (int i = 0; i < items.length(); i++) {
                    JSONObject row = items.getJSONObject(i);
                    String src = row.getString("url");
                    if (!PhotoUrl.isSafe(src)) continue;
                    collected.add(new Photo(src, row.optInt("index", i + 1),
                        row.optInt("width", 0), row.optInt("height", 0)));
                }
                if (collected.isEmpty()) throw new IllegalArgumentException("Nenhuma foto utilizável foi encontrada.");
                runOnUiThread(() -> {
                    if (destroyed) return;
                    photos.clear();
                    photos.addAll(collected);
                    postId = id;
                    title.setText(postTitle);
                    hint.setText(photos.size() + " fotos · toque na imagem para ampliar");
                    loading.setVisibility(View.GONE);
                    drawCards();
                    status.setText("Escolha as fotos e toque em Salvar.");
                    active = false;
                    updateSelection();
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (destroyed) return;
                    loading.setVisibility(View.GONE);
                    status.setText("Erro ao consultar: " + friendlyError(error));
                    active = false;
                });
            }
        });
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private void drawCards() {
        cards.removeAllViews();
        for (int start = 0; start < photos.size(); start += 2) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            cards.addView(row, new LinearLayout.LayoutParams(-1, -2));
            for (int n = start; n < Math.min(start + 2, photos.size()); n++) {
                Photo p = photos.get(n);
                LinearLayout card = new LinearLayout(this);
                card.setOrientation(LinearLayout.VERTICAL);
                card.setPadding(dp(4), dp(5), dp(4), dp(5));
                row.addView(card, new LinearLayout.LayoutParams(0, -2, 1f));

                ImageView picture = new ImageView(this);
                picture.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(164)));
                picture.setBackgroundColor(Color.rgb(33, 47, 66));
                picture.setScaleType(ImageView.ScaleType.CENTER_CROP);
                picture.setContentDescription("Prévia da foto " + p.index);
                picture.setOnClickListener(v -> showLarge(p));
                card.addView(picture);
                p.preview = picture;

                CheckBox check = new CheckBox(this);
                check.setText("Foto " + p.index + (p.width > 0 ? " · " + p.width + "×" + p.height : ""));
                check.setTextSize(11);
                check.setTextColor(Color.WHITE);
                check.setButtonTintList(android.content.res.ColorStateList.valueOf(Color.rgb(104, 229, 192)));
                check.setChecked(true);
                check.setOnCheckedChangeListener((button, checked) -> updateSelection());
                card.addView(check);
                p.check = check;
                previews.execute(() -> {
                    try {
                        Bitmap image = PhotoTransfer.preview(p.url);
                        runOnUiThread(() -> {
                            if (destroyed) { image.recycle(); return; }
                            p.bitmap = image;
                            p.preview.setImageBitmap(image);
                        });
                    } catch (Exception ignored) {
                        runOnUiThread(() -> {
                            if (!destroyed && p.preview != null) {
                                p.preview.setContentDescription("Foto " + p.index + ": prévia indisponível");
                            }
                        });
                    }
                });
            }
        }
    }

    private void showLarge(Photo photo) {
        if (photo.bitmap == null) {
            status.setText("A prévia desta foto não está disponível. Você ainda pode salvá-la.");
            return;
        }
        ImageView view = new ImageView(this);
        view.setImageBitmap(photo.bitmap);
        view.setAdjustViewBounds(true);
        view.setScaleType(ImageView.ScaleType.FIT_CENTER);
        int padding = dp(12);
        view.setPadding(padding, padding, padding, padding);
        new AlertDialog.Builder(this)
            .setTitle("Foto " + photo.index)
            .setView(view)
            .setPositiveButton("Fechar", null)
            .show();
    }

    private void checkAll(boolean state) {
        if (active) return;
        for (Photo p : photos) if (p.check != null) p.check.setChecked(state);
        updateSelection();
    }

    private void updateSelection() {
        int count = 0;
        for (Photo p : photos) if (p.check != null && p.check.isChecked()) count++;
        saveButton.setEnabled(!active && count > 0);
        saveButton.setText(count > 0 ? "Salvar " + count + (count == 1 ? " foto" : " fotos") : "Selecione uma foto");
        selectAll.setEnabled(!active && !photos.isEmpty());
        clearAll.setEnabled(!active && !photos.isEmpty());
    }

    private void saveSelected() {
        if (active) return;
        List<Photo> chosen = new ArrayList<>();
        for (Photo p : photos) if (p.check != null && p.check.isChecked()) chosen.add(p);
        if (chosen.isEmpty()) return;
        cancelled.set(false);
        active = true;
        saveButton.setEnabled(false);
        selectAll.setEnabled(false);
        clearAll.setEnabled(false);
        cancelButton.setVisibility(View.VISIBLE);
        work.execute(() -> {
            int completed = 0;
            String failure = null;
            for (Photo photo : chosen) {
                if (cancelled.get()) break;
                final int position = completed + 1;
                runOnUiThread(() -> status.setText("Salvando foto " + position + " de " + chosen.size() + "…"));
                try {
                    Uri saved = PhotoTransfer.save(this, photo.url, postId, photo.index, cancelled,
                        (done, total) -> { /* The item counter avoids UI flooding. */ });
                    if (saved != null) completed++;
                } catch (PhotoTransfer.Cancelled error) {
                    break;
                } catch (Exception error) {
                    failure = friendlyError(error);
                    break;
                }
            }
            final int savedCount = completed;
            final String failureText = failure;
            runOnUiThread(() -> {
                if (destroyed) return;
                active = false;
                cancelButton.setVisibility(View.GONE);
                updateSelection();
                if (cancelled.get()) status.setText("Cancelado. " + savedCount + " foto(s) já salva(s).");
                else if (failureText != null) status.setText(savedCount + " foto(s) salva(s). Erro: " + failureText);
                else status.setText("✅ " + savedCount + " foto(s) salva(s) em Imagens/SocialVault!");
            });
        });
    }

    private static String friendlyError(Exception error) {
        String msg = error.getMessage();
        if (msg == null || msg.trim().isEmpty()) return "Falha ao acessar a publicação.";
        return msg.length() <= 170 ? msg : msg.substring(0, 170) + "…";
    }

    @Override protected void onDestroy() {
        destroyed = true;
        cancelled.set(true);
        work.shutdownNow();
        previews.shutdownNow();
        super.onDestroy();
    }
}
