# Canal propio de importancia alta, ejecutado como shell mediante app_process.
# No instala APK, no lee SMS y no modifica canales de otras aplicaciones.
.class public Lcom/claro/tools/Popup;
.super Ljava/lang/Object;

.method public static main([Ljava/lang/String;)V
    .locals 14

    invoke-static {}, Landroid/os/Looper;->prepareMainLooper()V
    invoke-static {}, Landroid/app/ActivityThread;->systemMain()Landroid/app/ActivityThread;
    move-result-object v0
    invoke-virtual {v0}, Landroid/app/ActivityThread;->getSystemContext()Landroid/app/ContextImpl;
    move-result-object v10

    const-string v0, "notification"
    invoke-static {v0}, Landroid/os/ServiceManager;->getService(Ljava/lang/String;)Landroid/os/IBinder;
    move-result-object v0
    invoke-static {v0}, Landroid/app/INotificationManager$Stub;->asInterface(Landroid/os/IBinder;)Landroid/app/INotificationManager;
    move-result-object v11
    const-string v12, "com.android.shell"
    const-string v13, "claro_demo_popup_v1"

    new-instance v0, Landroid/app/NotificationChannel;
    const-string v1, "Claro - Demo flotante"
    const/4 v2, 0x4
    invoke-direct {v0, v13, v1, v2}, Landroid/app/NotificationChannel;-><init>(Ljava/lang/String;Ljava/lang/CharSequence;I)V
    invoke-static {v0}, Ljava/util/Collections;->singletonList(Ljava/lang/Object;)Ljava/util/List;
    move-result-object v1
    new-instance v0, Landroid/content/pm/ParceledListSlice;
    invoke-direct {v0, v1}, Landroid/content/pm/ParceledListSlice;-><init>(Ljava/util/List;)V
    invoke-interface {v11, v12, v0}, Landroid/app/INotificationManager;->createNotificationChannels(Ljava/lang/String;Landroid/content/pm/ParceledListSlice;)V

    new-instance v0, Landroid/app/Notification$Builder;
    invoke-direct {v0, v10, v13}, Landroid/app/Notification$Builder;-><init>(Landroid/content/Context;Ljava/lang/String;)V
    invoke-virtual {v10}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v1
    const-string v2, "stat_notify_chat"
    const-string v3, "drawable"
    const-string v4, "android"
    invoke-virtual {v1, v2, v3, v4}, Landroid/content/res/Resources;->getIdentifier(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)I
    move-result v1
    invoke-virtual {v0, v1}, Landroid/app/Notification$Builder;->setSmallIcon(I)Landroid/app/Notification$Builder;

    const/4 v1, 0x0
    aget-object v1, p0, v1
    invoke-virtual {v0, v1}, Landroid/app/Notification$Builder;->setContentTitle(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;
    const/4 v1, 0x1
    aget-object v2, p0, v1
    invoke-virtual {v0, v2}, Landroid/app/Notification$Builder;->setContentText(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;
    const-string v3, "msg"
    invoke-virtual {v0, v3}, Landroid/app/Notification$Builder;->setCategory(Ljava/lang/String;)Landroid/app/Notification$Builder;
    const-string v3, "Mensaje de prueba"
    invoke-virtual {v0, v3}, Landroid/app/Notification$Builder;->setSubText(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;

    # Un tercer argumento adjunta una imagen local ya transferida por el lanzador.
    array-length v3, p0
    const/4 v4, 0x3
    if-lt v3, v4, :text_style
    const/4 v3, 0x2
    aget-object v9, p0, v3
    new-instance v8, Landroid/graphics/BitmapFactory$Options;
    invoke-direct {v8}, Landroid/graphics/BitmapFactory$Options;-><init>()V
    const/4 v3, 0x1
    iput-boolean v3, v8, Landroid/graphics/BitmapFactory$Options;->inJustDecodeBounds:Z
    invoke-static {v9, v8}, Landroid/graphics/BitmapFactory;->decodeFile(Ljava/lang/String;Landroid/graphics/BitmapFactory$Options;)Landroid/graphics/Bitmap;
    iget v7, v8, Landroid/graphics/BitmapFactory$Options;->outWidth:I
    iget v4, v8, Landroid/graphics/BitmapFactory$Options;->outHeight:I
    if-lez v7, :invalid_image
    if-lez v4, :invalid_image
    const/4 v6, 0x1
    const/16 v5, 0x400
    :sample_image
    if-gt v7, v5, :shrink_image
    if-le v4, v5, :decode_image
    :shrink_image
    shr-int/lit8 v7, v7, 0x1
    shr-int/lit8 v4, v4, 0x1
    shl-int/lit8 v6, v6, 0x1
    goto :sample_image
    :decode_image
    iput v6, v8, Landroid/graphics/BitmapFactory$Options;->inSampleSize:I
    const/4 v3, 0x0
    iput-boolean v3, v8, Landroid/graphics/BitmapFactory$Options;->inJustDecodeBounds:Z
    invoke-static {v9, v8}, Landroid/graphics/BitmapFactory;->decodeFile(Ljava/lang/String;Landroid/graphics/BitmapFactory$Options;)Landroid/graphics/Bitmap;
    move-result-object v7
    if-eqz v7, :invalid_image
    invoke-virtual {v0, v7}, Landroid/app/Notification$Builder;->setLargeIcon(Landroid/graphics/Bitmap;)Landroid/app/Notification$Builder;
    new-instance v3, Landroid/app/Notification$BigPictureStyle;
    invoke-direct {v3}, Landroid/app/Notification$BigPictureStyle;-><init>()V
    invoke-virtual {v3, v7}, Landroid/app/Notification$BigPictureStyle;->bigPicture(Landroid/graphics/Bitmap;)Landroid/app/Notification$BigPictureStyle;
    invoke-virtual {v3, v2}, Landroid/app/Notification$BigPictureStyle;->setSummaryText(Ljava/lang/CharSequence;)Landroid/app/Notification$BigPictureStyle;
    sget v4, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v5, 0x1f
    if-lt v4, v5, :apply_style
    const/4 v4, 0x1
    invoke-virtual {v3, v4}, Landroid/app/Notification$BigPictureStyle;->showBigPictureWhenCollapsed(Z)Landroid/app/Notification$BigPictureStyle;
    goto :apply_style

    :invalid_image
    new-instance v1, Ljava/lang/IllegalArgumentException;
    const-string v2, "No se pudo decodificar la imagen de la notificacion"
    invoke-direct {v1, v2}, Ljava/lang/IllegalArgumentException;-><init>(Ljava/lang/String;)V
    throw v1

    :text_style
    new-instance v3, Landroid/app/Notification$BigTextStyle;
    invoke-direct {v3}, Landroid/app/Notification$BigTextStyle;-><init>()V
    invoke-virtual {v3, v2}, Landroid/app/Notification$BigTextStyle;->bigText(Ljava/lang/CharSequence;)Landroid/app/Notification$BigTextStyle;
    :apply_style
    invoke-virtual {v0, v3}, Landroid/app/Notification$Builder;->setStyle(Landroid/app/Notification$Style;)Landroid/app/Notification$Builder;
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/app/Notification$Builder;->setPriority(I)Landroid/app/Notification$Builder;
    invoke-virtual {v0, v1}, Landroid/app/Notification$Builder;->setAutoCancel(Z)Landroid/app/Notification$Builder;
    invoke-virtual {v0}, Landroid/app/Notification$Builder;->build()Landroid/app/Notification;
    move-result-object v5

    move-object v0, v11
    move-object v1, v12
    move-object v2, v12
    const-string v3, "claro-demo-popup"
    const/16 v4, 0x7ea
    invoke-static {}, Landroid/os/UserHandle;->myUserId()I
    move-result v6
    invoke-interface/range {v0 .. v6}, Landroid/app/INotificationManager;->enqueueNotificationWithTag(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;ILandroid/app/Notification;I)V

    sget-object v0, Ljava/lang/System;->out:Ljava/io/PrintStream;
    const-string v1, "popup-posted"
    invoke-virtual {v0, v1}, Ljava/io/PrintStream;->println(Ljava/lang/String;)V
    const/4 v0, 0x0
    invoke-static {v0}, Ljava/lang/System;->exit(I)V
    return-void
.end method
