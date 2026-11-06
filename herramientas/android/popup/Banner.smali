# Tarjeta flotante de demostración. Vive sólo durante esta ejecución de ADB.
.class public Lcom/claro/tools/Banner;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;
.implements Landroid/view/View$OnClickListener;

.field private manager:Landroid/view/WindowManager;
.field private view:Landroid/view/View;

.method public constructor <init>(Landroid/view/WindowManager;Landroid/view/View;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/claro/tools/Banner;->manager:Landroid/view/WindowManager;
    iput-object p2, p0, Lcom/claro/tools/Banner;->view:Landroid/view/View;
    return-void
.end method

.method public run()V
    .locals 2
    iget-object v0, p0, Lcom/claro/tools/Banner;->manager:Landroid/view/WindowManager;
    iget-object v1, p0, Lcom/claro/tools/Banner;->view:Landroid/view/View;
    invoke-interface {v0, v1}, Landroid/view/WindowManager;->removeViewImmediate(Landroid/view/View;)V
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "banner-closed"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    const/4 v0, 0x0
    invoke-static {v0}, Ljava/lang/System;->exit(I)V
    return-void
.end method

.method public onClick(Landroid/view/View;)V
    .locals 0
    invoke-virtual {p0}, Lcom/claro/tools/Banner;->run()V
    return-void
.end method

.method private static dp(Landroid/content/Context;I)I
    .locals 2
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v0
    iget v0, v0, Landroid/util/DisplayMetrics;->density:F
    int-to-float v1, p1
    mul-float/2addr v0, v1
    invoke-static {v0}, Ljava/lang/Math;->round(F)I
    move-result v0
    return v0
.end method

# Inicializa el contexto de aplicación que las vistas esperan fuera de Zygote.
# Referencia: Genymobile/scrcpy, server/.../Workarounds.java (fillAppInfo/fillAppContext).
.method private static field(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    .locals 2
    invoke-virtual {p1, p2}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object v0
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    invoke-virtual {v0, p0, p3}, Ljava/lang/reflect/Field;->set(Ljava/lang/Object;Ljava/lang/Object;)V
    return-void
.end method

.method private static prepareApplication(Landroid/content/Context;)V
    .locals 8
    const-string v0, "android.app.ActivityThread$AppBindData"
    invoke-static {v0}, Ljava/lang/Class;->forName(Ljava/lang/String;)Ljava/lang/Class;
    move-result-object v0
    const/4 v1, 0x0
    new-array v2, v1, [Ljava/lang/Class;
    invoke-virtual {v0, v2}, Ljava/lang/Class;->getDeclaredConstructor([Ljava/lang/Class;)Ljava/lang/reflect/Constructor;
    move-result-object v2
    const/4 v3, 0x1
    invoke-virtual {v2, v3}, Ljava/lang/reflect/Constructor;->setAccessible(Z)V
    new-array v3, v1, [Ljava/lang/Object;
    invoke-virtual {v2, v3}, Ljava/lang/reflect/Constructor;->newInstance([Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v2
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;
    move-result-object v4
    const-string v3, "appInfo"
    invoke-static {v2, v0, v3, v4}, Lcom/claro/tools/Banner;->field(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    invoke-static {}, Landroid/app/ActivityThread;->currentActivityThread()Landroid/app/ActivityThread;
    move-result-object v5
    const-class v6, Landroid/app/ActivityThread;
    const-string v3, "mBoundApplication"
    invoke-static {v5, v6, v3, v2}, Lcom/claro/tools/Banner;->field(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    const-class v0, Lcom/claro/tools/BannerApplication;
    invoke-static {v0, p0}, Landroid/app/Instrumentation;->newApplication(Ljava/lang/Class;Landroid/content/Context;)Landroid/app/Application;
    move-result-object v2
    const-string v3, "mInitialApplication"
    invoke-static {v5, v6, v3, v2}, Lcom/claro/tools/Banner;->field(Ljava/lang/Object;Ljava/lang/Class;Ljava/lang/String;Ljava/lang/Object;)V
    return-void
.end method

.method private static text(Landroid/content/Context;Ljava/lang/String;IIZ)Landroid/widget/TextView;
    .locals 2
    new-instance v0, Landroid/widget/TextView;
    invoke-direct {v0, p0}, Landroid/widget/TextView;-><init>(Landroid/content/Context;)V
    invoke-virtual {v0, p1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    int-to-float v1, p2
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setTextSize(F)V
    invoke-virtual {v0, p3}, Landroid/widget/TextView;->setTextColor(I)V
    if-eqz p4, :normal
    sget-object v1, Landroid/graphics/Typeface;->DEFAULT_BOLD:Landroid/graphics/Typeface;
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setTypeface(Landroid/graphics/Typeface;)V
    :normal
    return-object v0
.end method

.method private static add(Landroid/widget/LinearLayout;Landroid/view/View;II)V
    .locals 1
    new-instance v0, Landroid/widget/LinearLayout$LayoutParams;
    invoke-direct {v0, p2, p3}, Landroid/widget/LinearLayout$LayoutParams;-><init>(II)V
    invoke-virtual {p0, p1, v0}, Landroid/widget/LinearLayout;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V
    return-void
.end method

.method private static bitmap(Ljava/lang/String;)Landroid/graphics/Bitmap;
    .locals 6
    new-instance v0, Landroid/graphics/BitmapFactory$Options;
    invoke-direct {v0}, Landroid/graphics/BitmapFactory$Options;-><init>()V
    const/4 v1, 0x1
    iput-boolean v1, v0, Landroid/graphics/BitmapFactory$Options;->inJustDecodeBounds:Z
    invoke-static {p0, v0}, Landroid/graphics/BitmapFactory;->decodeFile(Ljava/lang/String;Landroid/graphics/BitmapFactory$Options;)Landroid/graphics/Bitmap;
    iget v2, v0, Landroid/graphics/BitmapFactory$Options;->outWidth:I
    iget v3, v0, Landroid/graphics/BitmapFactory$Options;->outHeight:I
    if-lez v2, :bad
    if-lez v3, :bad
    const/16 v4, 0x400
    :sample
    if-gt v2, v4, :shrink
    if-le v3, v4, :decode
    :shrink
    shr-int/lit8 v2, v2, 0x1
    shr-int/lit8 v3, v3, 0x1
    shl-int/lit8 v1, v1, 0x1
    goto :sample
    :decode
    iput v1, v0, Landroid/graphics/BitmapFactory$Options;->inSampleSize:I
    const/4 v1, 0x0
    iput-boolean v1, v0, Landroid/graphics/BitmapFactory$Options;->inJustDecodeBounds:Z
    invoke-static {p0, v0}, Landroid/graphics/BitmapFactory;->decodeFile(Ljava/lang/String;Landroid/graphics/BitmapFactory$Options;)Landroid/graphics/Bitmap;
    move-result-object v5
    if-eqz v5, :bad
    return-object v5
    :bad
    new-instance v0, Ljava/lang/IllegalArgumentException;
    const-string v1, "No se pudo cargar la imagen del banner"
    invoke-direct {v0, v1}, Ljava/lang/IllegalArgumentException;-><init>(Ljava/lang/String;)V
    throw v0
.end method

.method public static main([Ljava/lang/String;)V
    .locals 14
    :try_start
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "banner-start"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    # app_process no hereda la precarga de fuentes de Zygote.
    invoke-static {}, Landroid/graphics/Typeface;->loadPreinstalledSystemFontMap()V
    invoke-static {}, Landroid/os/Looper;->prepareMainLooper()V
    invoke-static {}, Landroid/app/ActivityThread;->systemMain()Landroid/app/ActivityThread;
    move-result-object v0
    invoke-virtual {v0}, Landroid/app/ActivityThread;->getSystemContext()Landroid/app/ContextImpl;
    move-result-object v0
    const-string v1, "com.android.shell"
    const/4 v2, 0x2
    invoke-virtual {v0, v1, v2}, Landroid/content/Context;->createPackageContext(Ljava/lang/String;I)Landroid/content/Context;
    move-result-object v11
    const-string v1, "display"
    invoke-virtual {v11, v1}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/hardware/display/DisplayManager;
    const/4 v1, 0x0
    invoke-virtual {v0, v1}, Landroid/hardware/display/DisplayManager;->getDisplay(I)Landroid/view/Display;
    move-result-object v0
    invoke-virtual {v11, v0}, Landroid/content/Context;->createDisplayContext(Landroid/view/Display;)Landroid/content/Context;
    move-result-object v11
    const/16 v0, 0x7f6
    const/4 v1, 0x0
    invoke-virtual {v11, v0, v1}, Landroid/content/Context;->createWindowContext(ILandroid/os/Bundle;)Landroid/content/Context;
    move-result-object v11
    invoke-static {v11}, Lcom/claro/tools/Banner;->prepareApplication(Landroid/content/Context;)V
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "banner-context-ready"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    const-string v0, "window"
    invoke-virtual {v11, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v10
    check-cast v10, Landroid/view/WindowManager;

    new-instance v12, Landroid/widget/LinearLayout;
    invoke-direct {v12, v11}, Landroid/widget/LinearLayout;-><init>(Landroid/content/Context;)V
    const/4 v0, 0x1
    invoke-virtual {v12, v0}, Landroid/widget/LinearLayout;->setOrientation(I)V
    const/16 v0, 0x14
    invoke-static {v11, v0}, Lcom/claro/tools/Banner;->dp(Landroid/content/Context;I)I
    move-result v0
    invoke-virtual {v12, v0, v0, v0, v0}, Landroid/view/View;->setPadding(IIII)V
    new-instance v1, Landroid/graphics/drawable/GradientDrawable;
    invoke-direct {v1}, Landroid/graphics/drawable/GradientDrawable;-><init>()V
    const/4 v2, -0x1
    invoke-virtual {v1, v2}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V
    int-to-float v0, v0
    invoke-virtual {v1, v0}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V
    invoke-virtual {v12, v1}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V
    invoke-virtual {v12, v0}, Landroid/view/View;->setElevation(F)V

    move-object v0, v11
    const-string v1, "CLARO  /  DEMOSTRACION"
    const/16 v2, 0xc
    const v3, -0x26e2d8
    const/4 v4, 0x1
    invoke-static {v0, v1, v2, v3, v4}, Lcom/claro/tools/Banner;->text(Landroid/content/Context;Ljava/lang/String;IIZ)Landroid/widget/TextView;
    move-result-object v1
    const/4 v2, -0x1
    const/4 v3, -0x2
    invoke-static {v12, v1, v2, v3}, Lcom/claro/tools/Banner;->add(Landroid/widget/LinearLayout;Landroid/view/View;II)V

    new-instance v1, Landroid/widget/ImageView;
    invoke-direct {v1, v11}, Landroid/widget/ImageView;-><init>(Landroid/content/Context;)V
    const/4 v0, 0x2
    aget-object v0, p0, v0
    invoke-static {v0}, Lcom/claro/tools/Banner;->bitmap(Ljava/lang/String;)Landroid/graphics/Bitmap;
    move-result-object v0
    invoke-virtual {v1, v0}, Landroid/widget/ImageView;->setImageBitmap(Landroid/graphics/Bitmap;)V
    sget-object v0, Landroid/widget/ImageView$ScaleType;->FIT_CENTER:Landroid/widget/ImageView$ScaleType;
    invoke-virtual {v1, v0}, Landroid/widget/ImageView;->setScaleType(Landroid/widget/ImageView$ScaleType;)V
    const/16 v0, 0x98
    invoke-static {v11, v0}, Lcom/claro/tools/Banner;->dp(Landroid/content/Context;I)I
    move-result v3
    const/4 v2, -0x1
    invoke-static {v12, v1, v2, v3}, Lcom/claro/tools/Banner;->add(Landroid/widget/LinearLayout;Landroid/view/View;II)V

    move-object v0, v11
    const/4 v1, 0x0
    aget-object v1, p0, v1
    const/16 v2, 0x18
    const v3, -0xe5e5e6
    const/4 v4, 0x1
    invoke-static {v0, v1, v2, v3, v4}, Lcom/claro/tools/Banner;->text(Landroid/content/Context;Ljava/lang/String;IIZ)Landroid/widget/TextView;
    move-result-object v1
    const/4 v2, -0x1
    const/4 v3, -0x2
    invoke-static {v12, v1, v2, v3}, Lcom/claro/tools/Banner;->add(Landroid/widget/LinearLayout;Landroid/view/View;II)V

    move-object v0, v11
    const/4 v1, 0x1
    aget-object v1, p0, v1
    const/16 v2, 0x10
    const v3, -0xb0b0b1
    const/4 v4, 0x0
    invoke-static {v0, v1, v2, v3, v4}, Lcom/claro/tools/Banner;->text(Landroid/content/Context;Ljava/lang/String;IIZ)Landroid/widget/TextView;
    move-result-object v1
    const/4 v2, 0x6
    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setMaxLines(I)V
    const/4 v2, -0x1
    const/4 v3, -0x2
    invoke-static {v12, v1, v2, v3}, Lcom/claro/tools/Banner;->add(Landroid/widget/LinearLayout;Landroid/view/View;II)V

    new-instance v13, Lcom/claro/tools/Banner;
    invoke-direct {v13, v10, v12}, Lcom/claro/tools/Banner;-><init>(Landroid/view/WindowManager;Landroid/view/View;)V
    new-instance v1, Landroid/widget/Button;
    invoke-direct {v1, v11}, Landroid/widget/Button;-><init>(Landroid/content/Context;)V
    const-string v0, "Cerrar demostracion"
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V
    invoke-virtual {v1, v13}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V
    const/4 v2, -0x1
    const/4 v3, -0x2
    invoke-static {v12, v1, v2, v3}, Lcom/claro/tools/Banner;->add(Landroid/widget/LinearLayout;Landroid/view/View;II)V

    # Ancho de pantalla menos margen; no toma el foco ni cubre la barra del sistema.
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "banner-layout-ready"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    new-instance v0, Landroid/view/WindowManager$LayoutParams;
    invoke-virtual {v11}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v1
    invoke-virtual {v1}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v1
    iget v1, v1, Landroid/util/DisplayMetrics;->widthPixels:I
    const/16 v2, 0x20
    invoke-static {v11, v2}, Lcom/claro/tools/Banner;->dp(Landroid/content/Context;I)I
    move-result v2
    sub-int/2addr v1, v2
    const/4 v2, -0x2
    const/16 v3, 0x7f6
    const/16 v4, 0x28
    const/4 v5, -0x3
    invoke-direct/range {v0 .. v5}, Landroid/view/WindowManager$LayoutParams;-><init>(IIIII)V
    const-string v1, "com.android.shell"
    iput-object v1, v0, Landroid/view/WindowManager$LayoutParams;->packageName:Ljava/lang/String;
    const/16 v1, 0x31
    iput v1, v0, Landroid/view/WindowManager$LayoutParams;->gravity:I
    const/16 v1, 0x18
    invoke-static {v11, v1}, Lcom/claro/tools/Banner;->dp(Landroid/content/Context;I)I
    move-result v1
    iput v1, v0, Landroid/view/WindowManager$LayoutParams;->y:I
    invoke-interface {v10, v12, v0}, Landroid/view/WindowManager;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V

    new-instance v0, Landroid/os/Handler;
    invoke-direct {v0}, Landroid/os/Handler;-><init>()V
    const/4 v1, 0x3
    aget-object v1, p0, v1
    invoke-static {v1}, Ljava/lang/Long;->parseLong(Ljava/lang/String;)J
    move-result-wide v2
    invoke-virtual {v0, v13, v2, v3}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z
    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "banner-shown"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    invoke-static {}, Landroid/os/Looper;->loop()V
    :try_end
    return-void
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :error
    :error
    move-exception v0
    sget-object v1, Ljava/lang/System;->out:Ljava/io/PrintStream;
    invoke-virtual {v1, v0}, Ljava/io/PrintStream;->println(Ljava/lang/Object;)V
    invoke-virtual {v0}, Ljava/lang/Throwable;->printStackTrace()V
    const/4 v0, 0x1
    invoke-static {v0}, Ljava/lang/System;->exit(I)V
    return-void
.end method
