package com.ew.system.spatial;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

import javax.imageio.ImageIO;

import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.MultiPolygon;
import org.locationtech.jts.geom.Polygon;
import org.springframework.stereotype.Service;

import com.ew.system.spatial.GeoDataLoader.DistrictFeature;
import com.ew.system.spatial.GeoDataLoader.RegionFeature;

@Service
public class MapRenderingService {
    // Matches src/builders/map_generator.py (lon_min, lat_min, lon_max, lat_max)
    private static final double LON_MIN = 28;
    private static final double LAT_MIN = -12;
    private static final double LON_MAX = 41;
    private static final double LAT_MAX = 1;

    private final GeoDataLoader loader;

    public MapRenderingService(GeoDataLoader loader) {
        this.loader = loader;
    }

    public Path renderRegionMap(Set<String> highlightedRegions,
                                  String fillHexColor,
                                  Path outputPath,
                                  int width,
                                  int height) {
        try {
            Files.createDirectories(outputPath.getParent());
        } catch (IOException e) {
            throw new RuntimeException("Failed to create output dir", e);
        }

        BufferedImage img = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g2 = img.createGraphics();
        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

        // Background
        g2.setColor(Color.WHITE);
        g2.fillRect(0, 0, width, height);

        Color fill = Color.decode(fillHexColor);
        Color noData = Color.WHITE;
        Color edge = Color.decode("#000000");

        g2.setStroke(new BasicStroke(1.0f));

        for (RegionFeature r : loader.getRegions()) {
            boolean on = highlightedRegions != null && highlightedRegions.contains(r.displayName());
            Color c = on ? fill : noData;
            drawGeometryPolygonFill(g2, r.geometry(), c, edge, width, height);
        }

        g2.dispose();
        try {
            ImageIO.write(img, "png", outputPath.toFile());
        } catch (IOException e) {
            throw new RuntimeException("Failed writing png", e);
        }

        return outputPath;
    }

    public Path renderDistrictMap(Set<String> highlightedDistricts,
                                    String fillHexColor,
                                    Path outputPath,
                                    int width,
                                    int height) {
        try {
            Files.createDirectories(outputPath.getParent());
        } catch (IOException e) {
            throw new RuntimeException("Failed to create output dir", e);
        }

        BufferedImage img = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g2 = img.createGraphics();
        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

        g2.setColor(Color.WHITE);
        g2.fillRect(0, 0, width, height);

        Color fill = Color.decode(fillHexColor);
        Color noData = Color.WHITE;
        Color edge = Color.decode("#333333");
        g2.setStroke(new BasicStroke(0.6f));

        for (DistrictFeature d : loader.getDistricts()) {
            boolean on = highlightedDistricts != null && highlightedDistricts.contains(d.displayName());
            Color c = on ? fill : noData;
            drawGeometryPolygonFill(g2, d.geometry(), c, edge, width, height);
        }

        g2.dispose();
        try {
            ImageIO.write(img, "png", outputPath.toFile());
        } catch (IOException e) {
            throw new RuntimeException("Failed writing png", e);
        }
        return outputPath;
    }

    public Path renderMultiTierDistrictMap(Set<String> majorWarningDistricts,
                                             Set<String> warningDistricts,
                                             Set<String> advisoryDistricts,
                                             Path outputPath,
                                             int width,
                                             int height) {
        try {
            Files.createDirectories(outputPath.getParent());
        } catch (IOException e) {
            throw new RuntimeException("Failed to create output dir", e);
        }

        BufferedImage img = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g2 = img.createGraphics();
        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

        g2.setColor(Color.WHITE);
        g2.fillRect(0, 0, width, height);

        Color major = Color.decode("#FF0000");
        Color warning = Color.decode("#FFA500");
        Color advisory = Color.decode("#FFFF00");
        Color edge = Color.decode("#333333");
        g2.setStroke(new BasicStroke(0.6f));

        for (DistrictFeature d : loader.getDistricts()) {
            Color c;
            if (majorWarningDistricts != null && majorWarningDistricts.contains(d.displayName())) {
                c = major;
            } else if (warningDistricts != null && warningDistricts.contains(d.displayName())) {
                c = warning;
            } else if (advisoryDistricts != null && advisoryDistricts.contains(d.displayName())) {
                c = advisory;
            } else {
                c = Color.WHITE;
            }
            drawGeometryPolygonFill(g2, d.geometry(), c, edge, width, height);
        }

        g2.dispose();
        try {
            ImageIO.write(img, "png", outputPath.toFile());
        } catch (IOException e) {
            throw new RuntimeException("Failed writing png", e);
        }
        return outputPath;
    }

    private void drawGeometryPolygonFill(Graphics2D g2,
                                          Geometry geometry,
                                          Color fill,
                                          Color edge,
                                          int width,
                                          int height) {
        if (geometry == null || geometry.isEmpty()) return;

        if (geometry instanceof Polygon poly) {
            drawPolygon(g2, poly, fill, edge, width, height);
            return;
        }
        if (geometry instanceof MultiPolygon mp) {
            for (int i = 0; i < mp.getNumGeometries(); i++) {
                Geometry g = mp.getGeometryN(i);
                if (g instanceof Polygon p) {
                    drawPolygon(g2, p, fill, edge, width, height);
                }
            }
        } else {
            // Fallback: attempt to polygonize by extracting polygon boundaries.
            // For production, replace with full geometry handling.
        }
    }

    private void drawPolygon(Graphics2D g2, Polygon poly, Color fill, Color edge,
                              int width, int height) {
        Coordinate[] coords = poly.getExteriorRing().getCoordinates();
        int n = coords.length;
        int[] xs = new int[n];
        int[] ys = new int[n];

        for (int i = 0; i < n; i++) {
            Coordinate c = coords[i];
            xs[i] = lonToX(c.x, width);
            ys[i] = latToY(c.y, height);
        }

        g2.setColor(fill);
        g2.fillPolygon(xs, ys, n);
        g2.setColor(edge);
        g2.drawPolygon(xs, ys, n);
    }

    private int lonToX(double lon, int pad, int width) {
        double t = (lon - LON_MIN) / (LON_MAX - LON_MIN);
        return (int) Math.round(t * (width - 1));
    }

    private int lonToX(double lon, int width) {
        return lonToX(lon, 0, width);
    }

    private int latToY(double lat, int height) {
        double t = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN);
        // lat_max -> top (y=0)
        return (int) Math.round((1 - t) * (height - 1));
    }

}

