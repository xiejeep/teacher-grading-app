export function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(img.src)
      resolve(img)
    }
    img.onerror = () => {
      URL.revokeObjectURL(img.src)
      reject(new Error('图片加载失败'))
    }
    img.src = URL.createObjectURL(file)
  })
}

export async function compressImage(file: File): Promise<File> {
  const sizeMB = file.size / (1024 * 1024)

  if (sizeMB > 10) {
    throw new Error('图片文件过大（超过10MB），请调整后重新上传')
  }
  if (sizeMB <= 1) {
    return file
  }

  const quality = sizeMB > 5 ? 0.7 : 0.5

  const img = await loadImage(file)
  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0)

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error('图片压缩失败'))),
      'image/jpeg',
      quality,
    )
  })

  const filename = file.name.replace(/\.\w+$/i, '.jpg')
  return new File([blob], filename, { type: 'image/jpeg' })
}
