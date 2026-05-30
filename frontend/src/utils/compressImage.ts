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

export async function rotateImage(file: File, degrees: 90 | 180 | 270 = 90): Promise<File> {
  const img = await loadImage(file)
  const w = img.naturalWidth
  const h = img.naturalHeight
  const cw = degrees % 180 === 0 ? w : h
  const ch = degrees % 180 === 0 ? h : w
  const canvas = document.createElement('canvas')
  canvas.width = cw
  canvas.height = ch
  const ctx = canvas.getContext('2d')!
  ctx.translate(cw / 2, ch / 2)
  ctx.rotate(degrees * Math.PI / 180)
  ctx.drawImage(img, -w / 2, -h / 2)
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(b => b ? resolve(b) : reject(new Error('旋转失败')), 'image/jpeg', 0.92)
  })
  const filename = file.name.replace(/\.\w+$/i, '.jpg')
  return new File([blob], filename, { type: 'image/jpeg' })
}
