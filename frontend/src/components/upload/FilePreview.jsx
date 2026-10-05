import { fileKind, formatBytes } from '../../lib/format'
import Icon from '../ui/Icon'

export default function FilePreview({ file }) {
  return (
    <div className="vd-file">
      <span className="vd-file-type" aria-hidden="true">
        {fileKind(file.name)}
      </span>
      <div className="vd-file-body">
        <p className="vd-file-name" title={file.name}>
          {file.name}
        </p>
        <p className="vd-file-meta">
          <span>{formatBytes(file.size)}</span>
          <span aria-hidden="true">·</span>
          <span className="vd-file-ok">
            <Icon name="check" size="sm" /> Ready
          </span>
        </p>
      </div>
    </div>
  )
}
