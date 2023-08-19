<?php
abstract class Stream {
  abstract protected function read($length);
  abstract public function seek($position);
  abstract public function position();
  abstract protected function getPos();
  abstract protected function setPos($pos);
  public function __get($name) {
    switch($name) {
      case 'position': return $this->getPos();
      case 'bool': return $this->readBoolean();
      case 'byte': return $this->readData(1);
      case 'short': return $this->readInt16();
      case 'ushort': return $this->readUint16();
      case 'long': return $this->readInt32();
      case 'ulong': return $this->readUint32();
      case 'longlong': return $this->readInt64();
      case 'ulonglong': return $this->readUint64();
      case 'float': return $this->readFloat();
      case 'double': return $this->readDouble();
      case 'string': return $this->readStringToNull();
      case 'line': return $this->readStringToReturn();
      default: throw new Exception("Access undefined field ${name} of class ".get_class($this));
    }
  }
  public function __set($name, $val) {
    switch($name) {
      case 'position': return $this->setPos($val);
      default: throw new Exception("Assign value to undefined field ${name} of class ".get_class($this));
    }
  }
  public $littleEndian = false;
  public $size;
  public function readStringToNull() {
    $s = '';
    while (ord($char = $this->read(1)) != 0) {
      $s .= $char;
    }
    return $s;
  }
  public function readStringAt($pos) {
    $current = $this->position;
    $this->position = $pos;
    $data = $this->string;
    $this->position = $current;
    return $data;
  }
  public function readStringToReturn() {
    $s = '';
    while ($this->position < $this->size && ($char = $this->read(1)) != "\n") {
      $s .= $char;
    }
    return trim($s,"\r");
  }
  public function readBoolean() {
    return ord($this->byte)>0;
  }
  public function readInt16() {
    $uint = $this->readUint16();
    $sint = unpack('s', pack('S', $uint))[1];
    return $sint;
  }
  public function readUint16() {
    $int = $this->read(2);
    if (strlen($int) != 2) return 0;
    return unpack($this->littleEndian?'v':'n', $int)[1];
  }
  public function readInt32() {
    $uint = $this->readUint32();
    $sint = unpack('l', pack('L', $uint))[1];
    return $sint;
  }
  public function readUint32() {
    $int = $this->read(4);
    if (strlen($int) != 4) return 0;
    return unpack($this->littleEndian?'V':'N', $int)[1];
  }
  public function readInt64() {
    $uint = $this->readUint64();
    $sint = unpack('q', pack('Q', $uint))[1];
    return $sint;
  }
  public function readUint64() {
    $int = $this->read(8);
    if (strlen($int) != 8) return 0;
    return unpack($this->littleEndian?'P':'J', $int)[1];
  }
  public function readFloat() {
    $int = $this->read(4);
    if (strlen($int) != 4) return 0;
    if (!$this->littleEndian) $int = $int[3].$int[2].$int[1].$int[0];
    return unpack(/*$this->littleEndian?'g':'G'*/ 'f', $int)[1];
  }
  public function readDouble() {
    $int = $this->read(8);
    if (strlen($int) != 8) return 0;
    if (!$this->littleEndian) $int = $int[7].$int[6].$int[5].$int[4].$int[3].$int[2].$int[1].$int[0];
    return unpack(/*$this->littleEndian?'e':'E'*/ 'd', $int)[1];
  }
  public function readData($size) {
    if ($size <= 0) return '';
    return $this->read($size);
  }
  public function readDataAt($pos, $size) {
    $current = $this->position;
    $this->position = $pos;
    $data = $this->readData($size);
    $this->position = $current;
    return $data;
  }
  public function alignStream($alignment) {
    $mod = $this->position % $alignment;
    if ($mod != 0) {
      $this->position += $alignment - $mod;
    }
  }
  public function readAlignedString($len) {
    $string = $this->readData($len);
    $this->alignStream(4);
    return $string;
  }
}
class FileStream extends Stream {
  private $f;
  function __construct($file) {
    $this->f = fopen($file, 'rb+');
    if ($this->f === false) {
      throw new Exception('Unable to open file');
    }
    $this->size = filesize($file);
  }
  function __destruct() {
    fclose($this->f);
  }
  protected function read($length) {
    return fread($this->f, $length);
  }
  public function write($newData) {
    fwrite($this->f, $newData);
    $pos = $this->position;
    fseek($this->f, 0, SEEK_END);
    $this->size = ftell($this->f);
    $this->position = $pos;
  }
  public function seek($position) {
    fseek($this->f, $position);
  }
  public function position() {
    return ftell($this->f);
  }
  protected function getPos() {
    return ftell($this->f);
  }
  protected function setPos($pos) {
    fseek($this->f, $pos);
  }
}
class MemoryStream extends Stream {
  private $data;
  private $offset;
  function __construct($data) {
    $this->data = $data;
    $this->size = strlen($data);
  }
  function __destruct() {
    $this->data = NULL;
  }
  protected function read($length) {
    $data = substr($this->data, $this->offset, $length);
    $this->offset += $length;
    return $data;
  }
  public function seek($position) {
    $this->offset = $position;
  }
  public function write($newData) {
    $this->data .= $newData;
    $this->size += strlen($newData);
  }
  public function position() {
    return $this->offset;
  }
  protected function getPos() {
    return $this->offset;
  }
  protected function setPos($pos) {
    $this->offset = $pos;
  }
}

function checkAndMoveFile(string $current, string $saveTo, int $modifiedTime = 0) {
  if (!file_exists($current)) return;
  $dir = pathinfo($saveTo, PATHINFO_DIRNAME);
  $format = pathinfo($saveTo, PATHINFO_EXTENSION);
  $saveTo = $dir.'/'.pathinfo($saveTo, PATHINFO_FILENAME);
  if (!file_exists($dir)) mkdir($dir, 0777, true);
  $saveToFull = $saveTo.'.'.$format;
  if (file_exists($saveToFull)) {
    $hash_current = hash_file('sha1', $current);
    $hash_previous = hash_file('sha1', $saveToFull);
    if ($hash_current === $hash_previous) {
      unlink($current);
      return;
    }
    $ftime = date('_Ymd_Hi', filemtime($saveToFull));
    rename($saveToFull, $saveTo.$ftime.'.'.$format);
  }
  rename($current, $saveToFull);
  if ($modifiedTime !== 0) {
    touch($saveToFull, $modifiedTime);
  }
}
function checkAndCreateFile(string $saveTo, string $data, int $modifiedTime = 0) {
  $dir = pathinfo($saveTo, PATHINFO_DIRNAME);
  $format = pathinfo($saveTo, PATHINFO_EXTENSION);
  $saveTo = $dir.'/'.pathinfo($saveTo, PATHINFO_FILENAME);
  if (!file_exists($dir)) mkdir($dir, 0777, true);
  $saveToFull = $saveTo.'.'.$format;
  if (file_exists($saveToFull)) {
    $hash_current = hash('sha1', $data);
    $hash_previous = hash_file('sha1', $saveToFull);
    if ($hash_current === $hash_previous) {
      return;
    }
    $ftime = date('_Ymd_Hi', filemtime($saveToFull));
    rename($saveToFull, $saveTo.$ftime.'.'.$format);
  }
  file_put_contents($saveToFull, $data);
  if ($modifiedTime !== 0) {
    touch($saveToFull, $modifiedTime);
  }
}
function lz4_uncompress_stream($data, $uncompressedSize) {
  return lz4_uncompress(pack('V', $uncompressedSize).$data);
}
function encrypt($string = '', $key = '', $iv = "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0") {
  return openssl_encrypt($string, 'AES-128-CBC', $key, OPENSSL_RAW_DATA, $iv);
}

function decrypt($string = '', $key = '', $iv = "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0") {
  $data = openssl_decrypt($string, 'AES-128-CBC', $key, OPENSSL_RAW_DATA+OPENSSL_ZERO_PADDING, $iv);
  $pad = ord(substr($data, -1, 1));
  return substr($data, 0, -$pad);
}

function extractBundle($bundle) {

  $header = $bundle->string;

  if ($header != 'UnityFS' && $header != 'UnityRaw') throw new Exception('unknown header: '.$header);

  $format = $bundle->long;
  $versionPlayer = $bundle->string;
  $versionEngine = $bundle->string;

  if ($format < 6) {
    $bundle->ulong;
    $bundle->ushort;
    $offset = $bundle->short;
    $bundle->ulong;
    $lzmaChunks = $bundle->long;
    $lzmaSize = 0;
    for($i=0; $i<$lzmaChunks; $i++) {
      $lzmaSize = $bundle->long;
      $bundle->ulong;
    }
    $bundle->position = $offset;

    // getFiles
    $fileCount = $bundle->long;
    $fileList = [];
    for ($i=0; $i<$fileCount; $i++) {
      $filename = $bundle->string;
      $fileOffset = $bundle->long + $offset;
      $fileSize = $bundle->long;
      $nextFile = $bundle->position;

      $bundle->position = $fileOffset;
      file_put_contents($filename, $bundle->readData($fileSize));
      $fileList[] = $filename;
      $bundle->position = $nextFile;
    }
    return $fileList;
  } else if ($format == 6) {
  } else if ($format == 7) {
  } else if ($format == 8) {
  } else {
    throw new Exception('unknown version: '.$format);
  }

  $bundle->longlong;
  $compressedSize = $bundle->long;
  $uncompressedSize = $bundle->long;
  $flag = $bundle->long;

  if (($flag & 128) != 0) {
    //throw new Exception('block info at end');
    if ($format >= 7) {
      $bundle->alignStream(16);
    }
    $pos = $bundle->position;
    $bundle->position = $bundle->size - $compressedSize;
    $blocksInfoBytes = $bundle->readData($compressedSize);
    $bundle->position = $pos;
  } else {
    if ($format >= 7) {
      $bundle->alignStream(16);
    }
    $blocksInfoBytes = $bundle->readData($compressedSize);
    if (($flag & 512) != 0) {
      $bundle->alignStream(16);
    }
  }

  switch ($flag & 63) {
    case 0:
      // Not compressed
      $uncompressedData = &$blocksInfoBytes;
      break;
    case 1:
      throw new Exception('lzma compressed block info');
    case 2:
    case 3:
      $uncompressedData = lz4_uncompress_stream($blocksInfoBytes, $uncompressedSize);
      break;
    default:
      throw 'unknown flag';
  }

  $blocksInfo = new MemoryStream($uncompressedData);
  unset($uncompressedData, $blocksInfoBytes);
  $blocksInfo->seek(16);
  $blockCount = $blocksInfo->long;
  fclose(fopen('--temp_decompress','wb'));
  $assetsData = new FileStream('--temp_decompress');

  for ($i=0; $i<$blockCount; $i++) {
    $uncompressedSize = $blocksInfo->long;
    $compressedSize = $blocksInfo->long;
    $flag = $blocksInfo->readInt16();
    //echo "${uncompressedSize}\t${compressedSize}\t${flag}\n";

    $chunkData = $bundle->readData($compressedSize);
    switch ($flag & 63) {
      case 0:
        // not compressed
        $assetsData->write($chunkData);
        break;
      case 1:
        // 7zip
        throw new Exception('lzma compressed chunk');
      case 2:
      case 3:
        $assetsData->write(lz4_uncompress_stream($chunkData, $uncompressedSize));
    }
    unset($chunkData);
  }

  //echo "\n";
  $entryInfo_count = $blocksInfo->long;
  $fileList = [];
  for ($i=0; $i<$entryInfo_count; $i++) {
    $entryInfoOffset = $blocksInfo->longlong;
    $entryInfoSize = $blocksInfo->longlong;
    $blocksInfo->long;
    $filename = $blocksInfo->string;
    //echo "${entryInfoOffset}\t${entryInfoSize}\t${filename}\n";

    $assetsData->position = $entryInfoOffset;
    $file = $assetsData->readData($entryInfoSize);
    /*$f = fopen($filename, 'wb');
    fwrite($f, $file);
    fclose($f);*/
    file_put_contents($filename, $file);
    unset($file);
    $fileList[] = $filename;
  }
  unset($assetsData);
  unlink('--temp_decompress');
  gc_collect_cycles();
  return $fileList;

}
