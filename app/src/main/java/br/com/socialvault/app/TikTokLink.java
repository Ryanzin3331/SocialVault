package br.com.socialvault.app;

import java.net.URI;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Recebe texto compartilhado ou URL, aceitando exclusivamente hosts oficiais. */
public final class TikTokLink {
    private static final Pattern URL = Pattern.compile("https?://[^\\s<>\\\"'`]+", Pattern.CASE_INSENSITIVE);
    private TikTokLink() { }

    public static String extract(String shareText) {
        if (shareText == null) return null;
        Matcher matcher = URL.matcher(shareText);
        while (matcher.find()) {
            String candidate = matcher.group().replaceFirst("[.,;:!?)\\u3002\\uff0c]+$", "");
            try {
                URI uri = new URI(candidate);
                String host = uri.getHost();
                if (host == null || uri.getUserInfo() != null) continue;
                host = host.toLowerCase(Locale.ROOT);
                if (!host.equals("tiktok.com") && !host.equals("www.tiktok.com")
                    && !host.equals("m.tiktok.com") && !host.equals("vm.tiktok.com")
                    && !host.equals("vt.tiktok.com")) continue;
                if (uri.getPort() != -1 && uri.getPort() != 80 && uri.getPort() != 443) continue;
                if (uri.getPath() == null || uri.getPath().equals("/") || uri.getPath().isEmpty()) continue;
                if (uri.getScheme() == null || !(uri.getScheme().equalsIgnoreCase("https") || uri.getScheme().equalsIgnoreCase("http"))) continue;
                return candidate;
            } catch (Exception ignored) { }
        }
        return null;
    }
}
